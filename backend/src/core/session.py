from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_db
from src.core.security import new_session_token, sign_payload, verify_signed_payload
from src.models.auth_session import AuthSession
from src.models.center import Center
from src.models.user import User


@dataclass(frozen=True)
class CurrentSession:
    session_id: str
    user: User
    center: Center | None

    @property
    def center_id(self) -> UUID | None:
        return self.user.center_id


async def create_session(
    db: AsyncSession, response: Response, user: User, settings: Settings | None = None
) -> CurrentSession:
    settings = settings or get_settings()
    session_id = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
    db.add(
        AuthSession(
            id=session_id, user_id=user.id, center_id=user.center_id, expires_at=expires_at
        )
    )
    cookie_value = sign_payload({"sid": session_id}, settings.session_secret)
    response.set_cookie(
        settings.session_cookie_name,
        cookie_value,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    center = await db.get(Center, user.center_id) if user.center_id is not None else None
    return CurrentSession(session_id=session_id, user=user, center=center)


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    auth_session = await db.get(AuthSession, session_id)
    if auth_session is not None:
        auth_session.revoked_at = datetime.now(UTC)


async def current_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentSession:
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if not cookie_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session")
    payload = verify_signed_payload(cookie_value, settings.session_secret)
    session_id = payload.get("sid") if payload else None
    if not isinstance(session_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    stmt: Select[tuple[AuthSession, User]] = (
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.id == session_id)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    auth_session, user = row
    now = datetime.now(UTC)
    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    center = await db.get(Center, user.center_id) if user.center_id is not None else None
    if center is not None and center.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center suspended")
    return CurrentSession(session_id=session_id, user=user, center=center)


async def current_user(session: CurrentSession = Depends(current_session)) -> User:
    return session.user
