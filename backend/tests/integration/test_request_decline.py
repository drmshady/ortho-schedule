"""T058: decline writes a reason + request_declined notification; only reception may
fulfill/decline (doctor attempt -> 403); the overdue flag is derived from preferred_to."""
from datetime import date, timedelta

from httpx import AsyncClient
from tests.helpers import local_slot_utc, seed_clinic

TEST_DATE = date(2026, 7, 6)


async def _login(client: AsyncClient, email: str, password: str) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def _create_request(client: AsyncClient, clinic, **extra) -> dict:
    return (
        await client.post(
            "/api/v1/requests",
            json={
                "patient_id": str(clinic.patient_id),
                "reason": "Follow-up",
                "urgency": "soon",
                "expected_duration_minutes": 30,
                **extra,
            },
        )
    ).json()


async def test_decline_writes_reason_and_notifies_doctor(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = await _create_request(client, clinic)

    await _login(client, clinic.reception_email, clinic.reception_password)
    declined = await client.post(
        f"/api/v1/requests/{request['id']}/decline",
        json={"decline_reason": "Doctor on leave that week"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert declined.json()["decline_reason"] == "Doctor on leave that week"

    await _login(client, clinic.doctor_email, clinic.reception_password)
    notifications = (await client.get("/api/v1/notifications")).json()
    declined_notes = [n for n in notifications if n["type"] == "request_declined"]
    assert len(declined_notes) == 1
    assert declined_notes[0]["payload"]["request_id"] == request["id"]


async def test_doctor_cannot_fulfill_or_decline(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)
    request = await _create_request(client, clinic)

    # Doctor (the requester) attempts to fulfill / decline their own request -> 403.
    starts_at = local_slot_utc(TEST_DATE, 9, 0, clinic.timezone)
    fulfill = await client.post(
        f"/api/v1/requests/{request['id']}/fulfill",
        json={
            "doctor_id": str(clinic.doctor_id),
            "patient_id": str(clinic.patient_id),
            "starts_at": starts_at.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert fulfill.status_code == 403

    decline = await client.post(
        f"/api/v1/requests/{request['id']}/decline", json={"decline_reason": "nope"}
    )
    assert decline.status_code == 403


async def test_overdue_flag_derived_from_preferred_to(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)

    past = await _create_request(
        client, clinic, preferred_to=(date.today() - timedelta(days=1)).isoformat()
    )
    future = await _create_request(
        client, clinic, preferred_to=(date.today() + timedelta(days=7)).isoformat()
    )
    none_window = await _create_request(client, clinic)

    listed = {r["id"]: r for r in (await client.get("/api/v1/requests")).json()}
    assert listed[past["id"]]["is_overdue"] is True
    assert listed[future["id"]]["is_overdue"] is False
    assert listed[none_window["id"]]["is_overdue"] is False
