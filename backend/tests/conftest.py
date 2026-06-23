import asyncio
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

# psycopg's async driver cannot run on Windows' default ProactorEventLoop; force selector.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.core.config import get_settings
from src.core.db import get_db
from src.main import create_app
from testcontainers.postgres import PostgresContainer

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Disposable PostgreSQL 16 database with btree_gist enabled for integration tests."""
    with PostgresContainer("postgres:16") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    url = cast(str, postgres_container.get_connection_url())
    # Normalize whatever driver testcontainers emits (psycopg2, bare) to async psycopg v3.
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@pytest.fixture()
def settings_env(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-change-me")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()


@pytest.fixture()
async def prepared_database(settings_env: None, database_url: str) -> AsyncIterator[str]:
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    # Alembic's async env.py calls asyncio.run(); run it off the test event loop.
    await asyncio.to_thread(command.upgrade, alembic_config, "head")
    yield database_url
    await asyncio.to_thread(command.downgrade, alembic_config, "base")


@pytest.fixture()
async def client(prepared_database: str) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(prepared_database, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    await engine.dispose()
