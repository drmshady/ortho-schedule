from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.appointment import AppointmentCreate, AppointmentOut
from src.schemas.request import (
    AppointmentRequestCreate,
    AppointmentRequestOut,
    RequestDecline,
)
from src.services.request_service import RequestWorkflowService
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("", response_model=list[AppointmentRequestOut])
async def list_requests(
    status_: str | None = Query(default=None, alias="status"),
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentRequestOut]:
    scope.require_role("reception", "center_admin", "doctor")
    requests = await RequestWorkflowService(db).list_requests(
        scope=scope, actor=session.user, status_filter=status_
    )
    return [AppointmentRequestOut.from_model(r) for r in requests]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AppointmentRequestOut)
async def create_request(
    payload: AppointmentRequestCreate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AppointmentRequestOut:
    scope.require_role("doctor")
    request = await RequestWorkflowService(db).create(
        scope=scope,
        actor=session.user,
        patient_id=payload.patient_id,
        reason=payload.reason,
        urgency=payload.urgency,
        expected_duration_minutes=payload.expected_duration_minutes,
        preferred_from=payload.preferred_from,
        preferred_to=payload.preferred_to,
        notes=payload.notes,
    )
    return AppointmentRequestOut.from_model(request)


@router.post(
    "/{request_id}/fulfill",
    status_code=status.HTTP_201_CREATED,
    response_model=AppointmentOut,
)
async def fulfill_request(
    request_id: UUID,
    payload: AppointmentCreate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AppointmentOut:
    scope.require_role("reception", "center_admin")
    appointment = await RequestWorkflowService(db).fulfill(
        scope=scope,
        actor=session.user,
        request_id=request_id,
        doctor_id=payload.doctor_id,
        patient_id=payload.patient_id,
        clinic_id=payload.clinic_id,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        confirm_patient_conflict=payload.confirm_patient_conflict,
    )
    return AppointmentOut.model_validate(appointment)


@router.post("/{request_id}/decline", response_model=AppointmentRequestOut)
async def decline_request(
    request_id: UUID,
    payload: RequestDecline,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AppointmentRequestOut:
    scope.require_role("reception")
    request = await RequestWorkflowService(db).decline(
        scope=scope,
        actor=session.user,
        request_id=request_id,
        decline_reason=payload.decline_reason,
    )
    return AppointmentRequestOut.from_model(request)
