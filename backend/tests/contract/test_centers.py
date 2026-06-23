"""T077: Contract tests for /centers (list/create) and /centers/{centerId}/status —
platform super-admin center provisioning (US4)."""
from httpx import AsyncClient
from tests.helpers import seed_clinic, seed_superadmin


async def _login(client: AsyncClient, email: str, password: str) -> int:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.status_code


async def test_superadmin_lists_centers(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    resp = await client.get("/api/v1/centers")
    assert resp.status_code == 200
    centers = resp.json()
    assert any(c["id"] == str(clinic.center_id) for c in centers)
    sample = centers[0]
    assert {"id", "name", "timezone", "grid_minutes", "status"} <= set(sample)


async def test_superadmin_creates_center_with_first_admin(
    client: AsyncClient, prepared_database: str
) -> None:
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    resp = await client.post(
        "/api/v1/centers",
        json={
            "name": "Riverside Clinic",
            "timezone": "Africa/Cairo",
            "grid_minutes": 20,
            "admin_email": "riverside.admin@example.com",
            "admin_temp_password": "TempPassword123!",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Riverside Clinic"
    assert body["status"] == "active"
    assert body["grid_minutes"] == 20


async def test_superadmin_suspends_and_reactivates_center(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    suspended = await client.put(
        f"/api/v1/centers/{clinic.center_id}/status", json={"status": "suspended"}
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    reactivated = await client.put(
        f"/api/v1/centers/{clinic.center_id}/status", json={"status": "active"}
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"


async def test_non_superadmin_cannot_access_centers(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    assert await _login(client, clinic.admin_email, clinic.reception_password) == 200

    assert (await client.get("/api/v1/centers")).status_code == 403
    created = await client.post(
        "/api/v1/centers",
        json={
            "name": "Blocked Clinic",
            "timezone": "Africa/Cairo",
            "admin_email": "blocked.admin@example.com",
            "admin_temp_password": "TempPassword123!",
        },
    )
    assert created.status_code == 403
    status_change = await client.put(
        f"/api/v1/centers/{clinic.center_id}/status", json={"status": "suspended"}
    )
    assert status_change.status_code == 403


async def test_create_center_defaults_to_saudi_timezone(
    client: AsyncClient, prepared_database: str
) -> None:
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    resp = await client.post(
        "/api/v1/centers",
        json={
            "name": "Default TZ Clinic",
            "admin_email": "default.tz.admin@example.com",
            "admin_temp_password": "TempPassword123!",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["timezone"] == "Asia/Riyadh"


async def test_superadmin_updates_center_timezone(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    resp = await client.put(
        f"/api/v1/centers/{clinic.center_id}", json={"timezone": "Asia/Riyadh"}
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Asia/Riyadh"


async def test_update_center_rejects_unknown_timezone(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    resp = await client.put(
        f"/api/v1/centers/{clinic.center_id}", json={"timezone": "Mars/Olympus_Mons"}
    )
    assert resp.status_code == 422


async def test_non_superadmin_cannot_update_timezone(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    assert await _login(client, clinic.admin_email, clinic.reception_password) == 200

    resp = await client.put(
        f"/api/v1/centers/{clinic.center_id}", json={"timezone": "Asia/Riyadh"}
    )
    assert resp.status_code == 403


async def test_create_center_duplicate_admin_email_conflicts(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    email, password = await seed_superadmin(prepared_database)
    assert await _login(client, email, password) == 200

    resp = await client.post(
        "/api/v1/centers",
        json={
            "name": "Collision Clinic",
            "timezone": "Africa/Cairo",
            "admin_email": clinic.admin_email,
            "admin_temp_password": "TempPassword123!",
        },
    )
    assert resp.status_code == 409
