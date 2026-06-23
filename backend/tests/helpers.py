from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.security import hash_password
from src.models.availability_template import AvailabilityTemplate
from src.models.center import Center
from src.models.doctor_profile import DoctorProfile
from src.models.patient import Patient
from src.models.user import User


async def seed_user(database_url: str, *, must_change_password: bool = True) -> tuple[str, str]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        center = Center(name="Downtown Clinic", timezone="Africa/Cairo", grid_minutes=15)
        db.add(center)
        await db.flush()
        user = User(
            center_id=center.id,
            role="reception",
            email="reception@example.com",
            display_name="Reception",
            password_hash=hash_password("TempPassword123!"),
            must_change_password=must_change_password,
            is_active=True,
        )
        db.add(user)
        await db.commit()
    await engine.dispose()
    return "reception@example.com", "TempPassword123!"


async def seed_superadmin(
    database_url: str,
    *,
    email: str = "super@example.com",
    password: str = "TempPassword123!",
    must_change_password: bool = False,
) -> tuple[str, str]:
    """Seed a platform super-admin (no center) for US4 provisioning flows."""
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        user = User(
            center_id=None,
            role="super_admin",
            email=email,
            display_name="Platform Admin",
            password_hash=hash_password(password),
            must_change_password=must_change_password,
            is_active=True,
        )
        db.add(user)
        await db.commit()
    await engine.dispose()
    return email, password


@dataclass
class SeededClinic:
    center_id: UUID
    timezone: str
    reception_email: str
    reception_password: str
    doctor_id: UUID
    doctor2_id: UUID
    doctor_email: str
    patient_id: UUID
    admin_id: UUID
    admin_email: str


async def seed_clinic(
    database_url: str,
    *,
    name: str = "Downtown Clinic",
    reception_email: str = "reception@example.com",
    doctor_email: str = "doctor@example.com",
    doctor2_email: str = "doctor2@example.com",
    admin_email: str = "admin@example.com",
    timezone: str = "Africa/Cairo",
) -> SeededClinic:
    """Seed a center with an active center-admin, reception user, two doctors (full-week
    availability), and one patient — the fixtures the US1/US3 acceptance flows need."""
    password = "TempPassword123!"
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        center = Center(name=name, timezone=timezone, grid_minutes=15)
        db.add(center)
        await db.flush()
        admin = User(
            center_id=center.id,
            role="center_admin",
            email=admin_email,
            display_name="Center Admin",
            password_hash=hash_password(password),
            must_change_password=False,
            is_active=True,
        )
        reception = User(
            center_id=center.id,
            role="reception",
            email=reception_email,
            display_name="Reception",
            password_hash=hash_password(password),
            must_change_password=False,
            is_active=True,
        )
        doctor = User(
            center_id=center.id,
            role="doctor",
            email=doctor_email,
            display_name="Dr. Example",
            password_hash=hash_password(password),
            must_change_password=False,
            is_active=True,
        )
        doctor2 = User(
            center_id=center.id,
            role="doctor",
            email=doctor2_email,
            display_name="Dr. Second",
            password_hash=hash_password(password),
            must_change_password=False,
            is_active=True,
        )
        db.add_all([admin, reception, doctor, doctor2])
        await db.flush()
        for doc in (doctor, doctor2):
            db.add(DoctorProfile(user_id=doc.id, center_id=center.id, specialty="General"))
            for weekday in range(7):
                db.add(
                    AvailabilityTemplate(
                        center_id=center.id,
                        doctor_id=doc.id,
                        weekday=weekday,
                        start_local=time(9, 0),
                        end_local=time(17, 0),
                    )
                )
        patient = Patient(
            center_id=center.id,
            full_name="Jane Doe",
            clinic_identifier="P-0001",
            phone="01000000000",
        )
        db.add(patient)
        await db.commit()
        clinic = SeededClinic(
            center_id=center.id,
            timezone=timezone,
            reception_email=reception_email,
            reception_password=password,
            doctor_id=doctor.id,
            doctor2_id=doctor2.id,
            doctor_email=doctor_email,
            patient_id=patient.id,
            admin_id=admin.id,
            admin_email=admin_email,
        )
    await engine.dispose()
    return clinic


def local_slot_utc(target_date: date, hour: int, minute: int, timezone_name: str) -> datetime:
    """Build a UTC datetime from a center-local wall-clock time (DST-correct)."""
    local = datetime.combine(target_date, time(hour, minute), ZoneInfo(timezone_name))
    return local.astimezone(ZoneInfo("UTC"))
