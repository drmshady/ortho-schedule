"""Doctor->reception appointment-request workflow (FR-014..FR-018).

State machine (each transition audited with actor + timestamp — Principle IV):
``pending -> fulfilled`` (reception books a concrete slot, delegating to ``BookingService``) or
``pending -> declined`` (reception, with a reason). Only reception may fulfill/decline; only a
doctor may create. Each resolution writes an in-app notification back to the requesting doctor.
"""
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.appointment import Appointment
from src.models.appointment_request import AppointmentRequest
from src.models.user import User
from src.services.booking_service import BookingService
from src.services.notification_service import NotificationService
from src.services.patient_service import PatientService
from src.tenancy.audit import write_audit_event
from src.tenancy.scope import CenterScope


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def is_overdue(request: AppointmentRequest, *, today: date | None = None) -> bool:
    """A pending request is overdue once its preferred window has passed (FR-018)."""
    if request.status != "pending" or request.preferred_to is None:
        return False
    return (today or date.today()) > request.preferred_to


class RequestWorkflowService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_in_scope(self, scope: CenterScope, request_id: UUID) -> AppointmentRequest:
        request = await self.db.get(AppointmentRequest, request_id)
        if request is None or request.center_id != scope.center_id:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Request not found")
        return request

    @staticmethod
    def _require_pending(request: AppointmentRequest) -> None:
        if request.status != "pending":
            raise _error(
                status.HTTP_409_CONFLICT,
                "invalid_transition",
                f"Cannot transition request from {request.status}",
            )

    async def create(
        self,
        *,
        scope: CenterScope,
        actor: User,
        patient_id: UUID,
        reason: str | None,
        urgency: str,
        expected_duration_minutes: int,
        preferred_from: date | None = None,
        preferred_to: date | None = None,
        notes: str | None = None,
    ) -> AppointmentRequest:
        if await PatientService(self.db).get_in_scope(scope, patient_id) is None:
            raise _error(status.HTTP_403_FORBIDDEN, "forbidden", "Patient is outside center scope")
        request = AppointmentRequest(
            center_id=scope.center_id,
            doctor_id=actor.id,
            patient_id=patient_id,
            reason=reason,
            urgency=urgency,
            expected_duration_minutes=expected_duration_minutes,
            preferred_from=preferred_from,
            preferred_to=preferred_to,
            notes=notes,
            status="pending",
        )
        self.db.add(request)
        await self.db.flush()
        await write_audit_event(
            self.db,
            actor=actor,
            action="request.create",
            target_type="appointment_request",
            target_id=request.id,
        )
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def fulfill(
        self,
        *,
        scope: CenterScope,
        actor: User,
        request_id: UUID,
        doctor_id: UUID,
        patient_id: UUID,
        starts_at: object,
        duration_minutes: int,
        clinic_id: UUID | None = None,
        confirm_patient_conflict: bool = False,
    ) -> Appointment:
        request = await self._get_in_scope(scope, request_id)
        self._require_pending(request)
        # Delegate the booking (atomic, integrity-gated). Commits on success.
        appointment = await BookingService(self.db).create(
            scope=scope,
            actor=actor,
            doctor_id=doctor_id,
            patient_id=patient_id,
            clinic_id=clinic_id,
            starts_at=starts_at,  # type: ignore[arg-type]
            duration_minutes=duration_minutes,
            source_request_id=request.id,
            confirm_patient_conflict=confirm_patient_conflict,
        )
        request.status = "fulfilled"
        request.resulting_appointment_id = appointment.id
        NotificationService(self.db).write(
            center_id=scope.center_id,
            recipient_user_id=request.doctor_id,
            type="request_fulfilled",
            payload={"request_id": str(request.id), "appointment_id": str(appointment.id)},
        )
        await write_audit_event(
            self.db,
            actor=actor,
            action="request.fulfill",
            target_type="appointment_request",
            target_id=request.id,
        )
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def decline(
        self,
        *,
        scope: CenterScope,
        actor: User,
        request_id: UUID,
        decline_reason: str,
    ) -> AppointmentRequest:
        request = await self._get_in_scope(scope, request_id)
        self._require_pending(request)
        request.status = "declined"
        request.decline_reason = decline_reason
        NotificationService(self.db).write(
            center_id=scope.center_id,
            recipient_user_id=request.doctor_id,
            type="request_declined",
            payload={"request_id": str(request.id)},
        )
        await write_audit_event(
            self.db,
            actor=actor,
            action="request.decline",
            target_type="appointment_request",
            target_id=request.id,
        )
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def list_requests(
        self,
        *,
        scope: CenterScope,
        actor: User,
        status_filter: str | None = None,
    ) -> list[AppointmentRequest]:
        stmt = select(AppointmentRequest).where(
            AppointmentRequest.center_id == scope.center_id
        )
        # Reception/center_admin see the whole queue; a doctor sees only their own requests.
        if actor.role == "doctor":
            stmt = stmt.where(AppointmentRequest.doctor_id == actor.id)
        if status_filter is not None:
            stmt = stmt.where(AppointmentRequest.status == status_filter)
        stmt = stmt.order_by(AppointmentRequest.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())
