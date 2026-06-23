"""T072: Staff-management integration (US3).

Verifies that deactivating a user blocks their login while their historical records
(appointments/requests) are retained, and that the staff list is strictly center-scoped
(other centers' users are invisible).
"""
from httpx import AsyncClient
from tests.helpers import seed_clinic


async def _login(client: AsyncClient, email: str, password: str) -> int:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.status_code


async def test_deactivation_blocks_login_but_retains_records(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    password = clinic.reception_password

    # The doctor creates a request (a record we expect to survive deactivation).
    assert await _login(client, clinic.doctor_email, password) == 200
    created = await client.post(
        "/api/v1/requests",
        json={
            "patient_id": str(clinic.patient_id),
            "reason": "Follow-up visit",
            "urgency": "soon",
            "expected_duration_minutes": 30,
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    # The admin deactivates the doctor.
    assert await _login(client, clinic.admin_email, password) == 200
    deactivated = await client.put(
        f"/api/v1/users/{clinic.doctor_id}", json={"is_active": False}
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    # The deactivated doctor can no longer log in.
    assert await _login(client, clinic.doctor_email, password) == 403

    # But their request is retained and still visible to reception.
    assert await _login(client, clinic.reception_email, password) == 200
    queue = await client.get("/api/v1/requests")
    assert queue.status_code == 200
    assert any(r["id"] == request_id for r in queue.json())


async def test_staff_list_is_center_scoped(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a = await seed_clinic(prepared_database)
    clinic_b = await seed_clinic(
        prepared_database,
        name="Uptown Clinic",
        reception_email="reception-b@example.com",
        doctor_email="doctor-b@example.com",
        doctor2_email="doctor2-b@example.com",
        admin_email="admin-b@example.com",
    )

    assert await _login(client, clinic_b.admin_email, clinic_b.reception_password) == 200
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}

    # Center B's admin sees only Center B's staff.
    assert clinic_b.doctor_email in emails
    assert clinic_b.reception_email in emails
    assert clinic_a.doctor_email not in emails
    assert clinic_a.reception_email not in emails
    assert clinic_a.admin_email not in emails


async def test_admin_cannot_edit_user_in_another_center(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a = await seed_clinic(prepared_database)
    clinic_b = await seed_clinic(
        prepared_database,
        name="Uptown Clinic",
        reception_email="reception-b@example.com",
        doctor_email="doctor-b@example.com",
        doctor2_email="doctor2-b@example.com",
        admin_email="admin-b@example.com",
    )

    assert await _login(client, clinic_b.admin_email, clinic_b.reception_password) == 200
    resp = await client.put(
        f"/api/v1/users/{clinic_a.doctor_id}", json={"is_active": False}
    )
    assert resp.status_code == 404
