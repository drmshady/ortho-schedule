"""T056: Contract tests for /notifications (list + mark read)."""
from datetime import date

from httpx import AsyncClient
from tests.helpers import local_slot_utc, seed_clinic

TEST_DATE = date(2026, 7, 6)


async def _login(client: AsyncClient, email: str, password: str) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_list_and_mark_read(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)

    # Doctor submits a request.
    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = (
        await client.post(
            "/api/v1/requests",
            json={
                "patient_id": str(clinic.patient_id),
                "reason": "Follow-up",
                "urgency": "soon",
                "expected_duration_minutes": 30,
            },
        )
    ).json()

    # Reception fulfills it -> doctor gets a notification.
    await _login(client, clinic.reception_email, clinic.reception_password)
    starts_at = local_slot_utc(TEST_DATE, 9, 0, clinic.timezone)
    await client.post(
        f"/api/v1/requests/{request['id']}/fulfill",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )

    # Doctor lists notifications.
    await _login(client, clinic.doctor_email, clinic.reception_password)
    listed = await client.get("/api/v1/notifications")
    assert listed.status_code == 200
    notifications = listed.json()
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification["type"] == "request_fulfilled"
    assert notification["is_read"] is False
    # Payload references ids only (no PHI).
    assert notification["payload"]["request_id"] == request["id"]

    unread = await client.get("/api/v1/notifications", params={"unread": "true"})
    assert len(unread.json()) == 1

    marked = await client.post(f"/api/v1/notifications/{notification['id']}/read")
    assert marked.status_code == 204

    unread_after = await client.get("/api/v1/notifications", params={"unread": "true"})
    assert unread_after.json() == []
