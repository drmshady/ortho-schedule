from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_db
from src.core.security import hash_password, verify_password
from src.core.session import CurrentSession, create_session, current_session, revoke_session
from src.models.center import Center
from src.models.user import User
from src.schemas.auth import ChangePasswordRequest, LoginRequest, Session

router = APIRouter(prefix="/auth", tags=["auth"])


def serialize_session(user: User) -> Session:
    return Session(
        user_id=user.id,
        role=user.role,
        center_id=user.center_id,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=Session)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Session:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    if user.center_id is not None:
        center = await db.get(Center, user.center_id)
        if center is None or center.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center suspended")
    await create_session(db, response, user, settings)
    await db.commit()
    return serialize_session(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: CurrentSession = Depends(current_session),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    await revoke_session(db, session.session_id)
    response.delete_cookie(settings.session_cookie_name, path="/")
    await db.commit()


@router.get("/session", response_model=Session)
async def read_session(session: CurrentSession = Depends(current_session)) -> Session:
    return serialize_session(session.user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    session: CurrentSession = Depends(current_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, session.user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_password", "message": "Current password is incorrect"},
        )
    session.user.password_hash = hash_password(payload.new_password)
    session.user.must_change_password = False
    session.user.updated_at = datetime.now(UTC)
    await db.commit()
