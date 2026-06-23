"""T034: patient-overlap warning, cancel frees the slot (retained in history),
and reschedule releases the old slot atomically."""
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


def _booking(clinic, doctor_id, starts_at, **extra) -> dict:
    return {
        "doctor_id": str(doctor_id),
        "patient_id": str(clinic.patient_id),
        "starts_at": starts_at.isoformat(),
        "duration_minutes": 30,
        **extra,
    }


async def test_patient_overlap_warns_until_confirmed(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)
    starts_at = local_slot_utc(TEST_DATE, 9, 0, clinic.timezone)

    first = await client.post(
        "/api/v1/appointments", json=_booking(clinic, clinic.doctor_id, starts_at)
    )
    assert first.status_code == 201

    # Same patient, overlapping time, different doctor -> patient_conflict warning.
    warn = await client.post(
        "/api/v1/appointments", json=_booking(clinic, clinic.doctor2_id, starts_at)
    )
    assert warn.status_code == 422
    assert warn.json()["code"] == "patient_conflict"

    confirmed = await client.post(
        "/api/v1/appointments",
        json=_booking(clinic, clinic.doctor2_id, starts_at, confirm_patient_conflict=True),
    )
    assert confirmed.status_code == 201


async def test_cancel_frees_slot_and_is_retained(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)
    starts_at = local_slot_utc(TEST_DATE, 12, 0, clinic.timezone)

    first = await client.post(
        "/api/v1/appointments", json=_booking(clinic, clinic.doctor_id, starts_at)
    )
    assert first.status_code == 201
    appointment_id = first.json()["id"]

    # Slot is taken: a second booking conflicts.
    blocked = await client.post(
        "/api/v1/patients", json={"full_name": "Sara Nabil", "phone": "01555444333"}
    )
    other_patient = blocked.json()["id"]
    conflict = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": other_patient,
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert conflict.status_code == 409

    cancelled = await client.put(
        f"/api/v1/appointments/{appointment_id}/status",
        json={"status": "cancelled", "cancel_reason": "freed"},
    )
    assert cancelled.status_code == 200

    # Slot is now free.
    rebooked = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": other_patient,
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert rebooked.status_code == 201

    # Cancelled appointment is retained in history.
    listed = await client.get("/api/v1/appointments", params={"doctor_id": str(clinic.doctor_id)})
    statuses = {a["id"]: a["status"] for a in listed.json()}
    assert statuses[appointment_id] == "cancelled"


async def test_reschedule_releases_old_slot(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)
    original = local_slot_utc(TEST_DATE, 13, 0, clinic.timezone)
    moved = local_slot_utc(TEST_DATE, 14, 0, clinic.timezone)

    first = await client.post(
        "/api/v1/appointments", json=_booking(clinic, clinic.doctor_id, original)
    )
    assert first.status_code == 201
    appointment_id = first.json()["id"]

    rescheduled = await client.post(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"starts_at": moved.isoformat(), "duration_minutes": 30},
    )
    assert rescheduled.status_code == 200

    # The original slot is now bookable for someone else (old slot released atomically).
    other = await client.post(
        "/api/v1/patients", json={"full_name": "Karim Adel", "phone": "01777666555"}
    )
    other_patient = other.json()["id"]
    rebooked = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": other_patient,
            "starts_at": original.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert rebooked.status_code == 201
