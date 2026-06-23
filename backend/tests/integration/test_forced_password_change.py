from httpx import AsyncClient
from tests.helpers import seed_user


async def test_forced_password_change_blocks_non_password_endpoint(
    client: AsyncClient, prepared_database: str
) -> None:
    email, password = await seed_user(prepared_database, must_change_password=True)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200

    blocked = await client.get("/api/v1/_scope-check")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "ChangedPassword123!"},
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/_scope-check")).status_code == 200
