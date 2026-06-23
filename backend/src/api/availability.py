from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.models.availability_exception import AvailabilityException
from src.models.availability_template import AvailabilityTemplate
from src.models.center import Center
from src.models.clinic import Clinic
from src.models.user import User
from src.schemas.availability import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionOut,
    AvailabilityTemplateCreate,
    AvailabilityTemplateOut,
    BookableInterval,
    DoctorOut,
)
from src.services.availability_resolver import resolve_bookable_intervals
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(tags=["availability"])


async def _require_doctor_in_scope(db: AsyncSession, scope: CenterScope, doctor_id: UUID) -> User:
    doctor = await db.get(User, doctor_id)
    if doctor is None or doctor.center_id != scope.center_id or doctor.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Doctor is outside center scope"},
        )
    return doctor


def _authorize_availability_edit(scope: CenterScope, target_doctor_id: UUID) -> None:
    """Center-admins and admin-flagged staff manage any doctor's availability; a plain doctor
    may only edit their own."""
    if scope.role == "center_admin" or scope.is_admin:
        return
    if scope.role == "doctor" and target_doctor_id == scope.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "forbidden", "message": "Not allowed to edit this availability"},
    )


@router.get("/doctors", response_model=list[DoctorOut])
async def list_doctors(
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[DoctorOut]:
    doctors = list(
        (
            await db.execute(
                select(User)
                .where(User.center_id == scope.center_id, User.role == "doctor", User.is_active)
                .order_by(User.display_name)
            )
        )
        .scalars()
        .all()
    )
    return [DoctorOut.model_validate(d) for d in doctors]


@router.get("/availability/templates", response_model=list[AvailabilityTemplateOut])
async def list_templates(
    doctor_id: UUID,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[AvailabilityTemplateOut]:
    await _require_doctor_in_scope(db, scope, doctor_id)
    rows = list(
        (
            await db.execute(
                select(AvailabilityTemplate).where(
                    AvailabilityTemplate.doctor_id == doctor_id,
                    AvailabilityTemplate.center_id == scope.center_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return [AvailabilityTemplateOut.model_validate(r) for r in rows]


@router.post(
    "/availability/templates",
    status_code=status.HTTP_201_CREATED,
    response_model=AvailabilityTemplateOut,
)
async def create_template(
    payload: AvailabilityTemplateCreate,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityTemplateOut:
    _authorize_availability_edit(scope, payload.doctor_id)
    await _require_doctor_in_scope(db, scope, payload.doctor_id)
    if payload.end_local <= payload.start_local:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_interval", "message": "end_local must be after start_local"},
        )
    if payload.clinic_id is not None:
        clinic = await db.get(Clinic, payload.clinic_id)
        if clinic is None or clinic.center_id != scope.center_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "Clinic is outside center scope"},
            )
    template = AvailabilityTemplate(
        center_id=scope.center_id,
        doctor_id=payload.doctor_id,
        clinic_id=payload.clinic_id,
        weekday=payload.weekday,
        start_local=payload.start_local,
        end_local=payload.end_local,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return AvailabilityTemplateOut.model_validate(template)


@router.delete("/availability/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> Response:
    template = await db.get(AvailabilityTemplate, template_id)
    if template is None or template.center_id != scope.center_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Availability template not found"},
        )
    _authorize_availability_edit(scope, template.doctor_id)
    await db.delete(template)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/availability/exceptions",
    status_code=status.HTTP_201_CREATED,
    response_model=AvailabilityExceptionOut,
)
async def create_exception(
    payload: AvailabilityExceptionCreate,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityExceptionOut:
    _authorize_availability_edit(scope, payload.doctor_id)
    await _require_doctor_in_scope(db, scope, payload.doctor_id)
    if payload.kind in ("override", "extra") and (
        payload.start_local is None or payload.end_local is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_interval", "message": "override/extra require start and end"},
        )
    if payload.clinic_id is not None:
        clinic = await db.get(Clinic, payload.clinic_id)
        if clinic is None or clinic.center_id != scope.center_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "Clinic is outside center scope"},
            )
    exception = AvailabilityException(
        center_id=scope.center_id,
        doctor_id=payload.doctor_id,
        clinic_id=payload.clinic_id,
        date=payload.date,
        kind=payload.kind,
        start_local=payload.start_local,
        end_local=payload.end_local,
        reason=payload.reason,
    )
    db.add(exception)
    await db.commit()
    await db.refresh(exception)
    return AvailabilityExceptionOut.model_validate(exception)


@router.get("/availability/exceptions", response_model=list[AvailabilityExceptionOut])
async def list_exceptions(
    doctor_id: UUID,
    date: date_type | None = None,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[AvailabilityExceptionOut]:
    await _require_doctor_in_scope(db, scope, doctor_id)
    stmt = select(AvailabilityException).where(
        AvailabilityException.doctor_id == doctor_id,
        AvailabilityException.center_id == scope.center_id,
    )
    if date is not None:
        stmt = stmt.where(AvailabilityException.date == date)
    rows = list((await db.execute(stmt)).scalars().all())
    return [AvailabilityExceptionOut.model_validate(r) for r in rows]


@router.delete("/availability/exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exception(
    exception_id: UUID,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> Response:
    exception = await db.get(AvailabilityException, exception_id)
    if exception is None or exception.center_id != scope.center_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Availability exception not found"},
        )
    _authorize_availability_edit(scope, exception.doctor_id)
    await db.delete(exception)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/availability/slots", response_model=list[BookableInterval])
async def get_slots(
    doctor_id: UUID,
    date: date_type,
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[BookableInterval]:
    await _require_doctor_in_scope(db, scope, doctor_id)
    center = await db.get(Center, scope.center_id)
    if center is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Center scope is required"},
        )
    templates = list(
        (
            await db.execute(
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
            await db.execute(
                select(AvailabilityException).where(
                    AvailabilityException.doctor_id == doctor_id,
                    AvailabilityException.center_id == scope.center_id,
                    AvailabilityException.date == date,
                )
            )
        )
        .scalars()
        .all()
    )
    intervals = resolve_bookable_intervals(
        target_date=date,
        timezone_name=center.timezone,
        templates=templates,
        exceptions=exceptions,
    )
    return [BookableInterval(start=iv.start, end=iv.end) for iv in intervals]
