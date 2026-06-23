from datetime import date

from httpx import AsyncClient
from tests.helpers import seed_clinic

TEST_DATE = date(2026, 7, 6)  # Monday


async def _login(client: AsyncClient, email: str, password: str) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_list_doctors(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.reception_email, clinic.reception_password)

    resp = await client.get("/api/v1/doctors")

    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert str(clinic.doctor_id) in ids


async def test_list_templates_and_slots(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.reception_email, clinic.reception_password)

    templates = await client.get(
        "/api/v1/availability/templates", params={"doctor_id": str(clinic.doctor_id)}
    )
    assert templates.status_code == 200
    assert len(templates.json()) == 7

    slots = await client.get(
        "/api/v1/availability/slots",
        params={"doctor_id": str(clinic.doctor_id), "date": TEST_DATE.isoformat()},
    )
    assert slots.status_code == 200
    assert len(slots.json()) == 1


async def test_doctor_can_author_template_and_block_exception(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)

    created = await client.post(
        "/api/v1/availability/templates",
        json={
            "doctor_id": str(clinic.doctor_id),
            "weekday": 0,
            "start_local": "18:00",
            "end_local": "20:00",
        },
    )
    assert created.status_code == 201

    blocked = await client.post(
        "/api/v1/availability/exceptions",
        json={
            "doctor_id": str(clinic.doctor_id),
            "date": TEST_DATE.isoformat(),
            "kind": "block",
        },
    )
    assert blocked.status_code == 201

    slots = await client.get(
        "/api/v1/availability/slots",
        params={"doctor_id": str(clinic.doctor_id), "date": TEST_DATE.isoformat()},
    )
    assert slots.status_code == 200
    assert slots.json() == []


async def test_admin_doctor_can_set_other_doctor_availability(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    # Center-admin grants admin privileges to a doctor (who keeps the doctor role).
    await _login(client, clinic.admin_email, clinic.reception_password)
    granted = await client.put(
        f"/api/v1/users/{clinic.doctor_id}", json={"is_admin": True}
    )
    assert granted.status_code == 200

    # That admin-doctor may now author availability for a *different* doctor.
    await _login(client, clinic.doctor_email, clinic.reception_password)
    created = await client.post(
        "/api/v1/availability/exceptions",
        json={
            "doctor_id": str(clinic.doctor2_id),
            "date": TEST_DATE.isoformat(),
            "kind": "override",
            "start_local": "08:00",
            "end_local": "12:00",
        },
    )
    assert created.status_code == 201

    listed = await client.get(
        "/api/v1/availability/exceptions", params={"doctor_id": str(clinic.doctor2_id)}
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_plain_doctor_cannot_set_other_doctor_availability(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.doctor_email, clinic.reception_password)

    resp = await client.post(
        "/api/v1/availability/exceptions",
        json={
            "doctor_id": str(clinic.doctor2_id),
            "date": TEST_DATE.isoformat(),
            "kind": "override",
            "start_local": "08:00",
            "end_local": "12:00",
        },
    )
    assert resp.status_code == 403
