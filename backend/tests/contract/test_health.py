from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient
from src.core.db import get_db
from src.main import create_app


async def test_health_reports_database_up_without_auth() -> None:
    class HealthySession:
        async def execute(self, _statement: object) -> None:
            return None

    async def override_get_db() -> AsyncIterator[HealthySession]:
        yield HealthySession()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
    assert "set-cookie" not in response.headers
    assert set(response.json()) == {"status", "database"}


async def test_health_reports_database_down_without_internals() -> None:
    class BrokenSession:
        async def execute(self, _statement: object) -> None:
            raise RuntimeError("database connection failed with secret details")

    async def override_get_db() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "down"}
    assert "secret details" not in response.text
    assert set(response.json()) == {"status", "database"}
