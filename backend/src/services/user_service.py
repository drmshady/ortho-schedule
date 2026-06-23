"""Center-admin staff management (US3, FR-019..FR-022).

A center-admin creates doctor/reception accounts within their own center (each issued a
temporary password with ``must_change_password=True``), edits display name / active state,
and deactivates/reactivates accounts. Deactivation blocks login but never deletes the user,
so their historical appointments/requests are retained. All actions are center-scoped and
audited (Principle II tenant isolation, Principle IV auditability).
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.models.doctor_profile import DoctorProfile
from src.models.user import User
from src.tenancy.audit import write_audit_event
from src.tenancy.scope import CenterScope

# Roles a center-admin is allowed to provision; privileged roles are never self-creatable.
ASSIGNABLE_ROLES = ("doctor", "reception")


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


class UserManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_in_scope(self, scope: CenterScope, user_id: UUID) -> User:
        user = await self.db.get(User, user_id)
        if user is None or user.center_id != scope.center_id:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "User not found")
        return user

    async def list_users(self, *, scope: CenterScope) -> list[User]:
        stmt = (
            select(User)
            .where(User.center_id == scope.center_id)
            .order_by(User.display_name)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(
        self,
        *,
        scope: CenterScope,
        actor: User,
        role: str,
        email: str,
        display_name: str,
        temp_password: str,
        specialty: str | None = None,
    ) -> User:
        if role not in ASSIGNABLE_ROLES:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "invalid_role",
                "A center-admin may only create doctor or reception accounts",
            )
        normalized_email = email.strip().lower()
        existing = await self.db.execute(select(User).where(User.email == normalized_email))
        if existing.scalar_one_or_none() is not None:
            raise _error(status.HTTP_409_CONFLICT, "duplicate_email", "Email already in use")

        user = User(
            center_id=scope.center_id,
            role=role,
            email=normalized_email,
            display_name=display_name,
            password_hash=hash_password(temp_password),
            must_change_password=True,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        if role == "doctor":
            self.db.add(
                DoctorProfile(user_id=user.id, center_id=scope.center_id, specialty=specialty)
            )
        await write_audit_event(
            self.db,
            actor=actor,
            action="user.create",
            target_type="app_user",
            target_id=user.id,
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(
        self,
        *,
        scope: CenterScope,
        actor: User,
        user_id: UUID,
        display_name: str | None = None,
        is_active: bool | None = None,
        is_admin: bool | None = None,
    ) -> User:
        user = await self._get_in_scope(scope, user_id)
        if display_name is not None:
            user.display_name = display_name
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None and is_admin != user.is_admin:
            # Center-admin privileges are only ever granted on top of a doctor/reception role,
            # never to the standalone center_admin owner or a super-admin.
            if user.role not in ASSIGNABLE_ROLES:
                raise _error(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "invalid_role",
                    "Admin privileges can only be granted to a doctor or reception account",
                )
            user.is_admin = is_admin
            await write_audit_event(
                self.db,
                actor=actor,
                action="user.grant_admin" if is_admin else "user.revoke_admin",
                target_type="app_user",
                target_id=user.id,
            )
        await write_audit_event(
            self.db,
            actor=actor,
            action="user.update",
            target_type="app_user",
            target_id=user.id,
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user
