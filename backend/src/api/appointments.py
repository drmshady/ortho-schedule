from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.appointment import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentReschedule,
    AppointmentStatusUpdate,
)
from src.services.booking_service import BookingService
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentOut])
async def list_appointments(
    doctor_id: UUID | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentOut]:
    appointments = await BookingService(db).list_appointments(
        scope=scope, doctor_id=doctor_id, from_dt=from_, to_dt=to
    )
    return [AppointmentOut.model_validate(a) for a in appointments]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AppointmentOut)
async def create_appointment(
    payload: AppointmentCreate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AppointmentOut:
    scope.require_role("reception", "center_admin")
    appointment = await BookingService(db).create(
        scope=scope,
        actor=session.user,
        doctor_id=payload.doctor_id,
        patient_id=payload.patient_id,
        patient_name=payload.patient_name,
        patient_clinic_identifier=payload.patient_clinic_identifier,
        clinic_id=payload.clinic_id,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        source_request_id=payload.source_request_id,
        confirm_patient_conflict=payload.confirm_patient_conflict,
    )
    return AppointmentOut.model_validate(appointment)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule_appointment(
    appointment_id: UUID,
    payload: AppointmentReschedule,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AppointmentOut:
    scope.require_role("reception", "center_admin")
    appointment = await BookingService(db).reschedule(
        scope=scope,
        actor=session.user,
        appointment_id=appointment_id,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        confirm_patient_conflict=payload.confirm_patient_conflict,
    )
    return AppointmentOut.model_validate(appointment)


@router.put("/{appointment_id}/status", response_model=AppointmentOut)
async def set_appointment_status(
    appointment_id: UUID,
    payload: AppointmentStatusUpdate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AppointmentOut:
    scope.require_role("reception", "center_admin")
    appointment = await BookingService(db).set_status(
        scope=scope,
        actor=session.user,
        appointment_id=appointment_id,
        new_status=payload.status,
        cancel_reason=payload.cancel_reason,
    )
    return AppointmentOut.model_validate(appointment)
