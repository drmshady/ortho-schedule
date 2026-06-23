from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.security import hash_password
from src.models.user import User


async def test_unscoped_super_admin_is_default_denied_on_tenant_dependency(
    client: AsyncClient, prepared_database: str
) -> None:
    engine = create_async_engine(prepared_database, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            User(
                center_id=None,
                role="super_admin",
                email="super@example.com",
                display_name="Super Admin",
                password_hash=hash_password("TempPassword123!"),
                must_change_password=False,
                is_active=True,
            )
        )
        await db.commit()
    await engine.dispose()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "super@example.com", "password": "TempPassword123!"},
    )
    assert login.status_code == 200

    denied = await client.get("/api/v1/_scope-check")

    assert denied.status_code == 403
    assert denied.json()["code"] == "forbidden"
