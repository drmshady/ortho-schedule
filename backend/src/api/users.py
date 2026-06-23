from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.user import UserCreate, UserOut, UserUpdate
from src.services.user_service import UserManagementService
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    _session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    scope.require_admin()
    users = await UserManagementService(db).list_users(scope=scope)
    return [UserOut.from_model(u) for u in users]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def create_user(
    payload: UserCreate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    scope.require_admin()
    user = await UserManagementService(db).create(
        scope=scope,
        actor=session.user,
        role=payload.role,
        email=payload.email,
        display_name=payload.display_name,
        temp_password=payload.temp_password,
        specialty=payload.specialty,
    )
    return UserOut.from_model(user)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    scope.require_admin()
    user = await UserManagementService(db).update(
        scope=scope,
        actor=session.user,
        user_id=user_id,
        display_name=payload.display_name,
        is_active=payload.is_active,
        is_admin=payload.is_admin,
    )
    return UserOut.from_model(user)
