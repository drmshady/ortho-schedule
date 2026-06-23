"""T079: Center provisioning lifecycle (US4).

Creating a center provisions its first center-admin atomically (that admin can log in and
manage only their own center). Suspending a center blocks all its users from logging in
until it is reactivated.
"""
from httpx import AsyncClient
from tests.helpers import seed_clinic, seed_superadmin


async def _login(client: AsyncClient, email: str, password: str) -> int:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.status_code


async def test_create_center_provisions_first_admin_atomically(
    client: AsyncClient, prepared_database: str
) -> None:
    su_email, su_password = await seed_superadmin(prepared_database)
    assert await _login(client, su_email, su_password) == 200

    resp = await client.post(
        "/api/v1/centers",
        json={
            "name": "Lakeside Clinic",
            "timezone": "Africa/Cairo",
            "admin_email": "lakeside.admin@example.com",
            "admin_temp_password": "TempPassword123!",
        },
    )
    assert resp.status_code == 201
    center_id = resp.json()["id"]

    # The provisioned admin can log in immediately and is forced to change their password.
    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "lakeside.admin@example.com", "password": "TempPassword123!"},
    )
    assert login.status_code == 200
    session = login.json()
    assert session["role"] == "center_admin"
    assert session["center_id"] == center_id
    assert session["must_change_password"] is True


async def test_suspending_center_blocks_logins_until_reactivated(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    su_email, su_password = await seed_superadmin(prepared_database)

    # Baseline: the center's reception can log in.
    assert await _login(client, clinic.reception_email, clinic.reception_password) == 200
    await client.post("/api/v1/auth/logout")

    # Super-admin suspends the center.
    assert await _login(client, su_email, su_password) == 200
    suspended = await client.put(
        f"/api/v1/centers/{clinic.center_id}/status", json={"status": "suspended"}
    )
    assert suspended.status_code == 200
    await client.post("/api/v1/auth/logout")

    # All of the center's users are now blocked from logging in.
    assert await _login(client, clinic.reception_email, clinic.reception_password) == 403
    assert await _login(client, clinic.admin_email, clinic.reception_password) == 403

    # Super-admin reactivates the center.
    assert await _login(client, su_email, su_password) == 200
    reactivated = await client.put(
        f"/api/v1/centers/{clinic.center_id}/status", json={"status": "active"}
    )
    assert reactivated.status_code == 200
    await client.post("/api/v1/auth/logout")

    # Logins succeed again.
    assert await _login(client, clinic.reception_email, clinic.reception_password) == 200
