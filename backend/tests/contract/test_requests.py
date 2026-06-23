"""T055: Contract tests for /requests (list/create), fulfill, and decline."""
from datetime import date, timedelta

from httpx import AsyncClient
from tests.helpers import local_slot_utc, seed_clinic

TEST_DATE = date(2026, 7, 6)
PAST_DATE = date.today() - timedelta(days=1)


async def _login(client: AsyncClient, email: str, password: str) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def _create_request(client: AsyncClient, clinic) -> dict:
    return (
        await client.post(
            "/api/v1/requests",
            json={
                "patient_id": str(clinic.patient_id),
                "reason": "Follow-up visit",
                "urgency": "soon",
                "expected_duration_minutes": 30,
            },
        )
    ).json()


async def test_doctor_creates_request_reception_lists_it(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)

    await _login(client, clinic.doctor_email, clinic.reception_password)
    created = await client.post(
        "/api/v1/requests",
        json={
            "patient_id": str(clinic.patient_id),
            "reason": "Follow-up visit",
            "urgency": "urgent",
            "expected_duration_minutes": 30,
            "preferred_to": PAST_DATE.isoformat(),
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "pending"
    assert body["urgency"] == "urgent"
    assert body["is_overdue"] is True  # preferred_to is in the past relative to "now"

    # Doctor sees their own request.
    own = await client.get("/api/v1/requests")
    assert own.status_code == 200
    assert any(r["id"] == body["id"] for r in own.json())

    # Reception sees it in the pending queue.
    await _login(client, clinic.reception_email, clinic.reception_password)
    queue = await client.get("/api/v1/requests", params={"status": "pending"})
    assert queue.status_code == 200
    assert any(r["id"] == body["id"] for r in queue.json())


async def test_reception_cannot_create_request(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.reception_email, clinic.reception_password)
    resp = await client.post(
        "/api/v1/requests",
        json={
            "patient_id": str(clinic.patient_id),
            "reason": "x",
            "urgency": "routine",
            "expected_duration_minutes": 30,
        },
    )
    assert resp.status_code == 403


async def test_fulfill_creates_appointment(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = await _create_request(client, clinic)

    await _login(client, clinic.reception_email, clinic.reception_password)
    starts_at = local_slot_utc(TEST_DATE, 9, 0, clinic.timezone)
    fulfilled = await client.post(
        f"/api/v1/requests/{request['id']}/fulfill",
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
    assert appointment["source_request_id"] == request["id"]


async def test_decline_sets_reason(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = await _create_request(client, clinic)

    await _login(client, clinic.reception_email, clinic.reception_password)
    declined = await client.post(
        f"/api/v1/requests/{request['id']}/decline",
        json={"decline_reason": "No capacity this week"},
    )
    assert declined.status_code == 200
    body = declined.json()
    assert body["status"] == "declined"
    assert body["decline_reason"] == "No capacity this week"
