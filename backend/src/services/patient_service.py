"""Patient registration and search with normalized duplicate detection (non-blocking)."""
import re
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.patient import Patient
from src.models.user import User
from src.tenancy.audit import write_audit_event
from src.tenancy.scope import CenterScope


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_identifier(value: str) -> str:
    return value.strip().lower()


# Auto-assigned clinic identifiers look like "P-0001"; the numeric suffix increments per center.
_AUTO_ID_PATTERN = re.compile(r"^P-(\d+)$", re.IGNORECASE)


class PatientService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, scope: CenterScope, actor: User, q: str | None) -> list[Patient]:
        stmt = select(Patient).where(Patient.center_id == scope.center_id)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(Patient.full_name.ilike(like), Patient.clinic_identifier.ilike(like))
            )
        stmt = stmt.order_by(Patient.full_name).limit(100)
        patients = list((await self.db.execute(stmt)).scalars().all())
        await write_audit_event(
            self.db, actor=actor, action="patient.read", target_type="patient", target_id=None
        )
        return patients

    async def find_duplicates(
        self, scope: CenterScope, full_name: str, clinic_identifier: str | None
    ) -> list[Patient]:
        norm_id = normalize_identifier(clinic_identifier) if clinic_identifier else None
        norm_name = normalize_name(full_name)
        existing = list(
            (
                await self.db.execute(
                    select(Patient).where(Patient.center_id == scope.center_id)
                )
            )
            .scalars()
            .all()
        )
        return [
            p
            for p in existing
            if (norm_id is not None and normalize_identifier(p.clinic_identifier) == norm_id)
            or normalize_name(p.full_name) == norm_name
        ]

    async def next_clinic_identifier(self, scope: CenterScope) -> str:
        """Assign the next sequential per-center clinic identifier (e.g. ``P-0001``)."""
        identifiers = (
            (
                await self.db.execute(
                    select(Patient.clinic_identifier).where(
                        Patient.center_id == scope.center_id
                    )
                )
            )
            .scalars()
            .all()
        )
        highest = 0
        for identifier in identifiers:
            match = _AUTO_ID_PATTERN.match((identifier or "").strip())
            if match:
                highest = max(highest, int(match.group(1)))
        return f"P-{highest + 1:04d}"

    async def create(self, scope: CenterScope, actor: User, **fields: object) -> Patient:
        patient = Patient(center_id=scope.center_id, **fields)
        self.db.add(patient)
        await self.db.flush()
        await write_audit_event(
            self.db,
            actor=actor,
            action="patient.create",
            target_type="patient",
            target_id=patient.id,
        )
        return patient

    async def get_or_create_by_identifier(
        self, scope: CenterScope, actor: User, *, full_name: str, clinic_identifier: str
    ) -> Patient:
        """Resolve a patient by clinic identifier within the center, creating one if absent.

        Lets reception/admin book a walk-in who is not yet registered: the patient row is
        created on the fly (name + ID), satisfying the appointment's patient FK.
        """
        norm_id = normalize_identifier(clinic_identifier)
        existing = list(
            (await self.db.execute(select(Patient).where(Patient.center_id == scope.center_id)))
            .scalars()
            .all()
        )
        for patient in existing:
            if normalize_identifier(patient.clinic_identifier) == norm_id:
                return patient
        return await self.create(
            scope, actor, full_name=full_name.strip(), clinic_identifier=clinic_identifier.strip()
        )

    async def get_in_scope(self, scope: CenterScope, patient_id: UUID) -> Patient | None:
        patient = await self.db.get(Patient, patient_id)
        if patient is None or patient.center_id != scope.center_id:
            return None
        return patient
