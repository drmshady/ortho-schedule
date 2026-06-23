from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.clinic import ClinicCreate, ClinicOut, ClinicUpdate
from src.services.clinic_service import ClinicService
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(prefix="/clinics", tags=["clinics"])


@router.get("", response_model=list[ClinicOut])
async def list_clinics(
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[ClinicOut]:
    # Any in-center staff may read the clinic directory (needed to book into a room).
    scope.require_role("reception", "center_admin", "doctor")
    clinics = await ClinicService(db).list(scope)
    return [ClinicOut.model_validate(c) for c in clinics]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClinicOut)
async def create_clinic(
    payload: ClinicCreate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> ClinicOut:
    scope.require_admin()
    clinic = await ClinicService(db).create(scope, session.user, name=payload.name)
    return ClinicOut.model_validate(clinic)


@router.put("/{clinic_id}", response_model=ClinicOut)
async def update_clinic(
    clinic_id: UUID,
    payload: ClinicUpdate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> ClinicOut:
    scope.require_admin()
    clinic = await ClinicService(db).update(
        scope, session.user, clinic_id, name=payload.name, is_active=payload.is_active
    )
    return ClinicOut.model_validate(clinic)


@router.delete("/{clinic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clinic(
    clinic_id: UUID,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> Response:
    scope.require_admin()
    await ClinicService(db).delete(scope, session.user, clinic_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
