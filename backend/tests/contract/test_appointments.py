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


async def test_create_list_reschedule_and_status(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)
    starts_at = local_slot_utc(TEST_DATE, 9, 0, clinic.timezone)

    created = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert created.status_code == 201
    appointment = created.json()
    assert appointment["status"] == "scheduled"
    assert appointment["origin"] == "direct"
    appointment_id = appointment["id"]

    listed = await client.get("/api/v1/appointments", params={"doctor_id": str(clinic.doctor_id)})
    assert listed.status_code == 200
    assert any(a["id"] == appointment_id for a in listed.json())

    new_start = local_slot_utc(TEST_DATE, 10, 0, clinic.timezone)
    rescheduled = await client.post(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"starts_at": new_start.isoformat(), "duration_minutes": 30},
    )
    assert rescheduled.status_code == 200

    cancelled = await client.put(
        f"/api/v1/appointments/{appointment_id}/status",
        json={"status": "cancelled", "cancel_reason": "patient request"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
