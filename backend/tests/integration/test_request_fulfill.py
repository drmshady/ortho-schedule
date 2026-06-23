"""T057: reception fulfill creates a scheduled appointment, marks the request fulfilled,
and writes a request_fulfilled notification to the requesting doctor."""
from datetime import date

from httpx import AsyncClient
from tests.helpers import local_slot_utc, seed_clinic

TEST_DATE = date(2026, 7, 6)


async def _login(client: AsyncClient, email: str, password: str) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_fulfill_books_marks_fulfilled_and_notifies(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)

    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = (
        await client.post(
            "/api/v1/requests",
            json={
                "patient_id": str(clinic.patient_id),
                "reason": "Crown fitting",
                "urgency": "soon",
                "expected_duration_minutes": 30,
            },
        )
    ).json()
    request_id = request["id"]

    await _login(client, clinic.reception_email, clinic.reception_password)
    starts_at = local_slot_utc(TEST_DATE, 10, 0, clinic.timezone)
    fulfilled = await client.post(
        f"/api/v1/requests/{request_id}/fulfill",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert fulfilled.status_code == 201
    appointment = fulfilled.json()
    assert appointment["status"] == "scheduled"
    assert appointment["origin"] == "request"

    # The appointment is visible on the doctor's schedule.
    listed = await client.get("/api/v1/appointments", params={"doctor_id": str(clinic.doctor_id)})
    assert any(a["id"] == appointment["id"] for a in listed.json())

    # Request is now fulfilled and links to the appointment.
    queue = await client.get("/api/v1/requests")
    fulfilled_request = next(r for r in queue.json() if r["id"] == request_id)
    assert fulfilled_request["status"] == "fulfilled"
    assert fulfilled_request["resulting_appointment_id"] == appointment["id"]

    # The requesting doctor received a request_fulfilled notification.
    await _login(client, clinic.doctor_email, clinic.reception_password)
    notifications = (await client.get("/api/v1/notifications")).json()
    fulfilled_notes = [n for n in notifications if n["type"] == "request_fulfilled"]
    assert len(fulfilled_notes) == 1
    assert fulfilled_notes[0]["payload"]["request_id"] == request_id


async def test_cannot_fulfill_an_already_resolved_request(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = (
        await client.post(
            "/api/v1/requests",
            json={
                "patient_id": str(clinic.patient_id),
                "reason": "x",
                "urgency": "routine",
                "expected_duration_minutes": 30,
            },
        )
    ).json()

    await _login(client, clinic.reception_email, clinic.reception_password)
    await client.post(
        f"/api/v1/requests/{request['id']}/decline", json={"decline_reason": "later"}
    )
    starts_at = local_slot_utc(TEST_DATE, 11, 0, clinic.timezone)
    second = await client.post(
        f"/api/v1/requests/{request['id']}/fulfill",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert second.status_code == 409
    assert second.json()["code"] == "invalid_transition"
