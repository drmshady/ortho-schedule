"""T033: bookings must align to the grid and fall inside resolved availability."""
from datetime import date

from httpx import AsyncClient
from tests.helpers import local_slot_utc, seed_clinic

TEST_DATE = date(2026, 7, 6)


async def _login_reception(client: AsyncClient, clinic) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": clinic.reception_email, "password": clinic.reception_password},
    )
    assert resp.status_code == 200


async def test_off_grid_start_is_rejected(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)
    starts_at = local_slot_utc(TEST_DATE, 9, 7, clinic.timezone)  # 09:07 is not on a 15-min grid

    resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "off_grid"


async def test_outside_availability_is_rejected(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)
    starts_at = local_slot_utc(TEST_DATE, 8, 0, clinic.timezone)  # before the 09:00 template start

    resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "outside_availability"
