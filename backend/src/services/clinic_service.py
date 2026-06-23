"""Center-scoped CRUD for clinics (numbered working units).

Clinics are managed by the center admin. Every row carries ``center_id`` and is created,
read, updated, and deleted strictly within the caller's center scope (default-deny).
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.clinic import Clinic
from src.models.user import User
from src.tenancy.audit import write_audit_event
from src.tenancy.scope import CenterScope


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


class ClinicService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, scope: CenterScope) -> list[Clinic]:
        rows = await self.db.execute(
            select(Clinic).where(Clinic.center_id == scope.center_id).order_by(Clinic.name)
        )
        return list(rows.scalars().all())

    async def get_in_scope(self, scope: CenterScope, clinic_id: UUID) -> Clinic:
        clinic = await self.db.get(Clinic, clinic_id)
        if clinic is None or clinic.center_id != scope.center_id:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Clinic not found")
        return clinic

    async def create(self, scope: CenterScope, actor: User, *, name: str) -> Clinic:
        clinic = Clinic(center_id=scope.center_id, name=name.strip(), is_active=True)
        self.db.add(clinic)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise _error(
                status.HTTP_409_CONFLICT,
                "duplicate_clinic",
                "A clinic with this name already exists in this center",
            ) from exc
        await write_audit_event(
            self.db, actor=actor, action="clinic.create", target_type="clinic", target_id=clinic.id
        )
        await self.db.commit()
        await self.db.refresh(clinic)
        return clinic

    async def update(
        self,
        scope: CenterScope,
        actor: User,
        clinic_id: UUID,
        *,
        name: str | None,
        is_active: bool | None,
    ) -> Clinic:
        clinic = await self.get_in_scope(scope, clinic_id)
        if name is not None:
            clinic.name = name.strip()
        if is_active is not None:
            clinic.is_active = is_active
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise _error(
                status.HTTP_409_CONFLICT,
                "duplicate_clinic",
                "A clinic with this name already exists in this center",
            ) from exc
        await write_audit_event(
            self.db, actor=actor, action="clinic.update", target_type="clinic", target_id=clinic.id
        )
        await self.db.commit()
        await self.db.refresh(clinic)
        return clinic

    async def delete(self, scope: CenterScope, actor: User, clinic_id: UUID) -> None:
        clinic = await self.get_in_scope(scope, clinic_id)
        await write_audit_event(
            self.db, actor=actor, action="clinic.delete", target_type="clinic", target_id=clinic.id
        )
        await self.db.delete(clinic)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise _error(
                status.HTTP_409_CONFLICT,
                "clinic_in_use",
                "This clinic has appointments; deactivate it instead of deleting",
            ) from exc
        await self.db.commit()
