from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.center import CenterCreate, CenterOut, CenterStatusUpdate, CenterUpdate
from src.services.center_service import CenterProvisioningService
from src.tenancy.scope import require_super_admin

router = APIRouter(prefix="/centers", tags=["centers"])


@router.get("", response_model=list[CenterOut])
async def list_centers(
    _session: CurrentSession = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[CenterOut]:
    centers = await CenterProvisioningService(db).list_centers()
    return [CenterOut.from_model(c) for c in centers]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CenterOut)
async def create_center(
    payload: CenterCreate,
    session: CurrentSession = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> CenterOut:
    center = await CenterProvisioningService(db).create(
        actor=session.user,
        name=payload.name,
        timezone=payload.timezone,
        grid_minutes=payload.grid_minutes,
        admin_email=payload.admin_email,
        admin_temp_password=payload.admin_temp_password,
        admin_role=payload.admin_role,
    )
    return CenterOut.from_model(center)


@router.put("/{center_id}", response_model=CenterOut)
async def update_center(
    center_id: UUID,
    payload: CenterUpdate,
    session: CurrentSession = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> CenterOut:
    center = await CenterProvisioningService(db).update_timezone(
        actor=session.user, center_id=center_id, timezone=payload.timezone
    )
    return CenterOut.from_model(center)


@router.put("/{center_id}/status", response_model=CenterOut)
async def set_center_status(
    center_id: UUID,
    payload: CenterStatusUpdate,
    session: CurrentSession = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> CenterOut:
    center = await CenterProvisioningService(db).set_status(
        actor=session.user, center_id=center_id, new_status=payload.status
    )
    return CenterOut.from_model(center)
