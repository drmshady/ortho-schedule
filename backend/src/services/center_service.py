"""Platform super-admin center provisioning (US4, FR-023..FR-026).

A super-admin creates centers (each with its first center-admin, atomically), configures
profiles, and suspends/reactivates centers. These are the only cross-center operations in the
system, and every one is audited (Principle II tenant isolation, Principle I auditability).
A suspended center blocks all of its users from logging in (enforced at the auth/session
layer) until it is reactivated.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.models.center import Center
from src.models.doctor_profile import DoctorProfile
from src.models.user import User
from src.tenancy.audit import write_audit_event

VALID_STATUSES = ("active", "suspended")
VALID_ADMIN_ROLES = ("center_admin", "doctor", "reception")


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


class CenterProvisioningService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_centers(self) -> list[Center]:
        stmt = select(Center).order_by(Center.name)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(
        self,
        *,
        actor: User,
        name: str,
        timezone: str,
        grid_minutes: int,
        admin_email: str,
        admin_temp_password: str,
        admin_role: str = "center_admin",
        admin_display_name: str = "Center Admin",
    ) -> Center:
        if admin_role not in VALID_ADMIN_ROLES:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "invalid_role",
                "admin_role must be center_admin, doctor, or reception",
            )
        normalized_email = admin_email.strip().lower()
        existing = await self.db.execute(select(User).where(User.email == normalized_email))
        if existing.scalar_one_or_none() is not None:
            raise _error(status.HTTP_409_CONFLICT, "duplicate_email", "Email already in use")

        center = Center(
            name=name,
            timezone=timezone,
            grid_minutes=grid_minutes,
            status="active",
            created_by=actor.id,
        )
        self.db.add(center)
        await self.db.flush()

        # A doctor/reception first admin keeps that working role and is granted center-admin
        # privileges via is_admin; a dedicated center_admin needs no extra flag.
        grants_admin = admin_role in ("doctor", "reception")
        admin = User(
            center_id=center.id,
            role=admin_role,
            email=normalized_email,
            display_name=admin_display_name,
            password_hash=hash_password(admin_temp_password),
            must_change_password=True,
            is_active=True,
            is_admin=grants_admin,
        )
        self.db.add(admin)
        await self.db.flush()
        if admin_role == "doctor":
            self.db.add(DoctorProfile(user_id=admin.id, center_id=center.id, specialty=None))
        await write_audit_event(
            self.db,
            actor=actor,
            action="center.create",
            target_type="center",
            target_id=center.id,
            center_id=center.id,
        )
        await self.db.commit()
        await self.db.refresh(center)
        return center

    async def update_timezone(self, *, actor: User, center_id: UUID, timezone: str) -> Center:
        center = await self.db.get(Center, center_id)
        if center is None:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Center not found")

        center.timezone = timezone
        await write_audit_event(
            self.db,
            actor=actor,
            action="center.update_timezone",
            target_type="center",
            target_id=center.id,
            center_id=center.id,
        )
        await self.db.commit()
        await self.db.refresh(center)
        return center

    async def set_status(self, *, actor: User, center_id: UUID, new_status: str) -> Center:
        if new_status not in VALID_STATUSES:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "invalid_status",
                "Center status must be 'active' or 'suspended'",
            )
        center = await self.db.get(Center, center_id)
        if center is None:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Center not found")

        center.status = new_status
        await write_audit_event(
            self.db,
            actor=actor,
            action=f"center.{'suspend' if new_status == 'suspended' else 'reactivate'}",
            target_type="center",
            target_id=center.id,
            center_id=center.id,
        )
        await self.db.commit()
        await self.db.refresh(center)
        return center
