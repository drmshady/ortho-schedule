"""Atomic appointment booking: create / reschedule / status, with all integrity gates.

Every mutating method runs in a single transaction. The no-double-booking invariant is
enforced by the PostgreSQL GiST exclusion constraint (Principle IV); a conflict surfaces as a
``409 double_booking``. Grid alignment, availability containment, and patient-overlap warnings
are validated server-side before the write.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.timezone import duration_is_grid_multiple, is_grid_aligned, utc_to_local
from src.models.appointment import Appointment
from src.models.availability_exception import AvailabilityException
from src.models.availability_template import AvailabilityTemplate
from src.models.center import Center
from src.models.clinic import Clinic
from src.models.doctor_profile import DoctorProfile
from src.models.user import User
from src.services.availability_resolver import covers, resolve_bookable_intervals
from src.tenancy.audit import write_audit_event
from src.tenancy.scope import CenterScope

_PG_EXCLUSION_VIOLATION = "23P01"
_CLINIC_EXCLUSION_CONSTRAINT = "ex_appointment_clinic_no_double_booking"
_ALLOWED_STATUS_TRANSITIONS = {"completed", "cancelled", "no_show"}


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


class BookingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_center(self, scope: CenterScope) -> Center:
        center = await self.db.get(Center, scope.center_id)
        if center is None:
            raise _error(status.HTTP_403_FORBIDDEN, "forbidden", "Center scope is required")
        return center

    async def _effective_grid(self, scope: CenterScope, center: Center, doctor_id: UUID) -> int:
        profile = await self.db.get(DoctorProfile, doctor_id)
        if profile is not None and profile.grid_minutes:
            return profile.grid_minutes
        return center.grid_minutes

    async def _require_doctor(self, scope: CenterScope, doctor_id: UUID) -> User:
        doctor = await self.db.get(User, doctor_id)
        if doctor is None or doctor.center_id != scope.center_id or doctor.role != "doctor":
            raise _error(status.HTTP_403_FORBIDDEN, "forbidden", "Doctor is outside center scope")
        return doctor

    async def _require_clinic(self, scope: CenterScope, clinic_id: UUID) -> Clinic:
        clinic = await self.db.get(Clinic, clinic_id)
        if clinic is None or clinic.center_id != scope.center_id:
            raise _error(status.HTTP_403_FORBIDDEN, "forbidden", "Clinic is outside center scope")
        if not clinic.is_active:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "inactive_clinic",
                "The selected clinic is inactive",
            )
        return clinic

    async def _validate_slot(
        self,
        *,
        scope: CenterScope,
        center: Center,
        doctor_id: UUID,
        starts_at: datetime,
        duration_minutes: int,
    ) -> tuple[datetime, datetime]:
        grid = await self._effective_grid(scope, center, doctor_id)
        if not is_grid_aligned(starts_at, grid, center.timezone) or not duration_is_grid_multiple(
            duration_minutes, grid
        ):
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "off_grid",
                "Start time and duration must align to the booking grid",
            )
        end = starts_at + timedelta(minutes=duration_minutes)
        local_date = utc_to_local(starts_at, center.timezone).date()
        templates = list(
            (
                await self.db.execute(
                    select(AvailabilityTemplate).where(
                        AvailabilityTemplate.doctor_id == doctor_id,
                        AvailabilityTemplate.center_id == scope.center_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        exceptions = list(
            (
                await self.db.execute(
                    select(AvailabilityException).where(
                        AvailabilityException.doctor_id == doctor_id,
                        AvailabilityException.center_id == scope.center_id,
                        AvailabilityException.date == local_date,
                    )
                )
            )
            .scalars()
            .all()
        )
        intervals = resolve_bookable_intervals(
            target_date=local_date,
            timezone_name=center.timezone,
            templates=templates,
            exceptions=exceptions,
        )
        if not covers(intervals, starts_at, end):
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "outside_availability",
                "Requested time is outside the doctor's resolved availability",
            )
        return starts_at, end

    async def _check_patient_overlap(
        self,
        *,
        scope: CenterScope,
        patient_id: UUID,
        starts_at: datetime,
        end: datetime,
        confirm: bool,
        exclude_id: UUID | None = None,
    ) -> None:
        if confirm:
            return
        existing = list(
            (
                await self.db.execute(
                    select(Appointment).where(
                        Appointment.center_id == scope.center_id,
                        Appointment.patient_id == patient_id,
                        Appointment.status == "scheduled",
                    )
                )
            )
            .scalars()
            .all()
        )
        for appt in existing:
            if exclude_id is not None and appt.id == exclude_id:
                continue
            appt_end = appt.starts_at + timedelta(minutes=appt.duration_minutes)
            if appt.starts_at < end and starts_at < appt_end:
                raise _error(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "patient_conflict",
                    "Patient already has an appointment overlapping this time",
                )

    async def _flush_or_conflict(self) -> None:
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            if getattr(exc.orig, "sqlstate", None) == _PG_EXCLUSION_VIOLATION:
                constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                if constraint == _CLINIC_EXCLUSION_CONSTRAINT:
                    raise _error(
                        status.HTTP_409_CONFLICT,
                        "clinic_double_booking",
                        "That clinic is already in use for an overlapping time",
                    ) from exc
                raise _error(
                    status.HTTP_409_CONFLICT,
                    "double_booking",
                    "The doctor is already booked for an overlapping time",
                ) from exc
            raise

    async def create(
        self,
        *,
        scope: CenterScope,
        actor: User,
        doctor_id: UUID,
        starts_at: datetime,
        duration_minutes: int,
        patient_id: UUID | None = None,
        patient_name: str | None = None,
        patient_clinic_identifier: str | None = None,
        clinic_id: UUID | None = None,
        source_request_id: UUID | None = None,
        confirm_patient_conflict: bool = False,
    ) -> Appointment:
        from src.services.patient_service import PatientService

        center = await self._load_center(scope)
        await self._require_doctor(scope, doctor_id)
        if clinic_id is not None:
            await self._require_clinic(scope, clinic_id)
        patient_service = PatientService(self.db)
        if patient_id is not None:
            patient = await patient_service.get_in_scope(scope, patient_id)
            if patient is None:
                raise _error(
                    status.HTTP_403_FORBIDDEN, "forbidden", "Patient is outside center scope"
                )
        elif patient_name and patient_clinic_identifier:
            # Walk-in: resolve or create the patient on the fly (not pre-registered).
            patient = await patient_service.get_or_create_by_identifier(
                scope,
                actor,
                full_name=patient_name,
                clinic_identifier=patient_clinic_identifier,
            )
        else:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "patient_required",
                "Provide an existing patient or a walk-in name and ID",
            )
        patient_id = patient.id

        starts_at = starts_at.astimezone(UTC)
        _, end = await self._validate_slot(
            scope=scope,
            center=center,
            doctor_id=doctor_id,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
        )
        await self._check_patient_overlap(
            scope=scope,
            patient_id=patient_id,
            starts_at=starts_at,
            end=end,
            confirm=confirm_patient_conflict,
        )
        appointment = Appointment(
            center_id=scope.center_id,
            doctor_id=doctor_id,
            patient_id=patient_id,
            clinic_id=clinic_id,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
            status="scheduled",
            origin="request" if source_request_id else "direct",
            source_request_id=source_request_id,
            created_by=actor.id,
        )
        self.db.add(appointment)
        await self._flush_or_conflict()
        await write_audit_event(
            self.db,
            actor=actor,
            action="appointment.create",
            target_type="appointment",
            target_id=appointment.id,
        )
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def reschedule(
        self,
        *,
        scope: CenterScope,
        actor: User,
        appointment_id: UUID,
        starts_at: datetime,
        duration_minutes: int,
        confirm_patient_conflict: bool = False,
    ) -> Appointment:
        appointment = await self._get_scheduled(scope, appointment_id)
        center = await self._load_center(scope)
        starts_at = starts_at.astimezone(UTC)
        _, end = await self._validate_slot(
            scope=scope,
            center=center,
            doctor_id=appointment.doctor_id,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
        )
        await self._check_patient_overlap(
            scope=scope,
            patient_id=appointment.patient_id,
            starts_at=starts_at,
            end=end,
            confirm=confirm_patient_conflict,
            exclude_id=appointment.id,
        )
        appointment.starts_at = starts_at
        appointment.duration_minutes = duration_minutes
        await self._flush_or_conflict()
        await write_audit_event(
            self.db,
            actor=actor,
            action="appointment.reschedule",
            target_type="appointment",
            target_id=appointment.id,
        )
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def set_status(
        self,
        *,
        scope: CenterScope,
        actor: User,
        appointment_id: UUID,
        new_status: str,
        cancel_reason: str | None = None,
    ) -> Appointment:
        appointment = await self._get_in_scope(scope, appointment_id)
        if appointment.status != "scheduled" or new_status not in _ALLOWED_STATUS_TRANSITIONS:
            raise _error(
                status.HTTP_409_CONFLICT,
                "invalid_transition",
                f"Cannot transition appointment from {appointment.status} to {new_status}",
            )
        appointment.status = new_status
        if new_status == "cancelled":
            appointment.cancel_reason = cancel_reason
        await write_audit_event(
            self.db,
            actor=actor,
            action=f"appointment.{new_status}",
            target_type="appointment",
            target_id=appointment.id,
        )
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def _get_in_scope(self, scope: CenterScope, appointment_id: UUID) -> Appointment:
        appointment = await self.db.get(Appointment, appointment_id)
        if appointment is None or appointment.center_id != scope.center_id:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Appointment not found")
        return appointment

    async def _get_scheduled(self, scope: CenterScope, appointment_id: UUID) -> Appointment:
        appointment = await self._get_in_scope(scope, appointment_id)
        if appointment.status != "scheduled":
            raise _error(
                status.HTTP_409_CONFLICT,
                "invalid_transition",
                "Only scheduled appointments can be rescheduled",
            )
        return appointment

    async def list_appointments(
        self,
        *,
        scope: CenterScope,
        doctor_id: UUID | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> list[Appointment]:
        stmt = select(Appointment).where(Appointment.center_id == scope.center_id)
        if doctor_id is not None:
            stmt = stmt.where(Appointment.doctor_id == doctor_id)
        if from_dt is not None:
            stmt = stmt.where(Appointment.starts_at >= from_dt.astimezone(UTC))
        if to_dt is not None:
            stmt = stmt.where(Appointment.starts_at < to_dt.astimezone(UTC))
        stmt = stmt.order_by(Appointment.starts_at)
        return list((await self.db.execute(stmt)).scalars().all())
