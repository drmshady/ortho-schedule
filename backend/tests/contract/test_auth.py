from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.models.user import User
from tests.helpers import seed_user


async def test_auth_login_session_change_password_and_logout(
    client: AsyncClient, prepared_database: str
) -> None:
    email, password = await seed_user(prepared_database)

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    assert "session=" in login.headers["set-cookie"]

    session = await client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["role"] == "reception"

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "Replacement123!"},
    )
    assert changed.status_code == 204

    session_after_change = await client.get("/api/v1/auth/session")
    assert session_after_change.status_code == 200
    assert session_after_change.json()["must_change_password"] is False

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/session")).status_code == 401


async def test_login_rejects_inactive_user(client: AsyncClient, prepared_database: str) -> None:
    email, password = await seed_user(prepared_database)
    engine = create_async_engine(prepared_database, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.is_active = False
        await db.commit()
    await engine.dispose()

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 403
