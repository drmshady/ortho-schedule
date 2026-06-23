"""T071: Contract tests for /users (list/create) and /users/{userId} (edit) — center-admin
staff management (US3)."""
from httpx import AsyncClient
from tests.helpers import seed_clinic


async def _login(client: AsyncClient, email: str, password: str) -> None:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_admin_lists_center_staff(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.admin_email, clinic.reception_password)

    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert clinic.reception_email in emails
    assert clinic.doctor_email in emails
    assert clinic.admin_email in emails


async def test_admin_creates_doctor(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.admin_email, clinic.reception_password)

    resp = await client.post(
        "/api/v1/users",
        json={
            "role": "doctor",
            "email": "new.doctor@example.com",
            "display_name": "Dr. New",
            "temp_password": "TempPassword123!",
            "specialty": "Pediatrics",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "doctor"
    assert body["email"] == "new.doctor@example.com"
    assert body["is_active"] is True
    assert body["must_change_password"] is True


async def test_admin_creates_reception(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.admin_email, clinic.reception_password)

    resp = await client.post(
        "/api/v1/users",
        json={
            "role": "reception",
            "email": "new.reception@example.com",
            "display_name": "Front Desk",
            "temp_password": "TempPassword123!",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "reception"


async def test_admin_edits_staff(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.admin_email, clinic.reception_password)

    resp = await client.put(
        f"/api/v1/users/{clinic.doctor_id}",
        json={"display_name": "Dr. Renamed", "is_active": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Dr. Renamed"
    assert body["is_active"] is False


async def test_admin_grants_admin_to_doctor_who_can_then_manage_staff(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.admin_email, clinic.reception_password)

    # The center-admin grants admin privileges to a doctor (who keeps the doctor role).
    granted = await client.put(
        f"/api/v1/users/{clinic.doctor_id}", json={"is_admin": True}
    )
    assert granted.status_code == 200
    body = granted.json()
    assert body["role"] == "doctor"
    assert body["is_admin"] is True

    # That doctor can now sign in and exercise center-admin actions (e.g. list staff).
    await _login(client, clinic.doctor_email, clinic.reception_password)
    listed = await client.get("/api/v1/users")
    assert listed.status_code == 200

    # ...and the privilege can be revoked again.
    revoked = await client.put(
        f"/api/v1/users/{clinic.doctor_id}", json={"is_admin": False}
    )
    assert revoked.status_code == 200
    assert revoked.json()["is_admin"] is False


async def test_non_admin_cannot_list_or_create_users(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.reception_email, clinic.reception_password)

    assert (await client.get("/api/v1/users")).status_code == 403
    created = await client.post(
        "/api/v1/users",
        json={
            "role": "doctor",
            "email": "blocked@example.com",
            "display_name": "Nope",
            "temp_password": "TempPassword123!",
        },
    )
    assert created.status_code == 403


async def test_admin_cannot_create_privileged_role(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login(client, clinic.admin_email, clinic.reception_password)

    resp = await client.post(
        "/api/v1/users",
        json={
            "role": "center_admin",
            "email": "escalate@example.com",
            "display_name": "Escalation",
            "temp_password": "TempPassword123!",
        },
    )
    assert resp.status_code == 422
