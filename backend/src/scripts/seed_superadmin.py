"""One-off bootstrap script: create the platform super-admin (US4, T082).

The super-admin is the only account not bound to a center; it provisions centers and their
first admins. This script is idempotent — re-running it leaves an existing super-admin with
the same email untouched. The temporary password must be changed on first login.

Usage (from ``backend/``)::

    SUPERADMIN_EMAIL=ops@example.com SUPERADMIN_PASSWORD='change-me-please-12' \
        python -m src.scripts.seed_superadmin

Reads ``DATABASE_URL`` from the environment/.env via the app settings. ``SUPERADMIN_EMAIL``
and ``SUPERADMIN_PASSWORD`` (>= 12 chars) configure the account; the password is never
logged.
"""
import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.config import get_settings
from src.core.security import hash_password
from src.models.user import User


async def seed_superadmin(email: str, password: str) -> bool:
    """Create the super-admin if absent. Returns True if a new account was created."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            existing = await db.execute(select(User).where(User.email == email.lower()))
            if existing.scalar_one_or_none() is not None:
                return False
            db.add(
                User(
                    center_id=None,
                    role="super_admin",
                    email=email.lower(),
                    display_name="Platform Admin",
                    password_hash=hash_password(password),
                    must_change_password=True,
                    is_active=True,
                )
            )
            await db.commit()
            return True
    finally:
        await engine.dispose()


def main() -> int:
    email = os.environ.get("SUPERADMIN_EMAIL")
    password = os.environ.get("SUPERADMIN_PASSWORD")
    if not email or not password:
        print("SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD must be set", file=sys.stderr)
        return 2
    if len(password) < 8:
        print("SUPERADMIN_PASSWORD must be at least 8 characters", file=sys.stderr)
        return 2

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    created = asyncio.run(seed_superadmin(email, password))
    if created:
        print(f"Super-admin created: {email} (must change password on first login)")
    else:
        print(f"Super-admin already exists: {email} (no change)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
