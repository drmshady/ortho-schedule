"""NON-NEGOTIABLE gate (T032 / Principle IV): concurrent double-booking contention.

Two simultaneous bookings of the same doctor and slot — exactly one must succeed; the other
must be rejected with ``409 double_booking`` by the GiST exclusion constraint.
"""
import asyncio
from datetime import date

from httpx import AsyncClient
from tests.helpers import local_slot_utc, seed_clinic

TEST_DATE = date(2026, 7, 6)


async def test_concurrent_same_slot_booking_allows_exactly_one(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": clinic.reception_email, "password": clinic.reception_password},
    )
    assert login.status_code == 200

    # Two distinct patients so the doctor exclusion constraint — not patient overlap — is the gate.
    second = await client.post(
        "/api/v1/patients", json={"full_name": "Mona Ali", "phone": "01999888777"}
    )
    assert second.status_code == 201
    second_patient_id = second.json()["id"]

    starts_at = local_slot_utc(TEST_DATE, 11, 0, clinic.timezone).isoformat()

    def booking(patient_id: str) -> dict:
        return {
            "doctor_id": str(clinic.doctor_id),
            "patient_id": patient_id,
            "starts_at": starts_at,
            "duration_minutes": 30,
        }

    first, secondary = await asyncio.gather(
        client.post("/api/v1/appointments", json=booking(str(clinic.patient_id))),
        client.post("/api/v1/appointments", json=booking(second_patient_id)),
    )

    statuses = sorted([first.status_code, secondary.status_code])
    assert statuses == [201, 409]
    conflict = first if first.status_code == 409 else secondary
    assert conflict.json()["code"] == "double_booking"
