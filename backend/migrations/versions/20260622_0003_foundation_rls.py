"""enable foundational row level security backstops

Revision ID: 20260622_0003
Revises: 20260622_0002
Create Date: 2026-06-22
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260622_0003"
down_revision: str | None = "20260622_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("app_user", "audit_event", "auth_session"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY app_user_center_isolation ON app_user
        USING (
            center_id IS NULL
            OR center_id::text = current_setting('app.center_id', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_event_center_isolation ON audit_event
        USING (
            center_id IS NULL
            OR center_id::text = current_setting('app.center_id', true)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY auth_session_center_isolation ON auth_session
        USING (
            center_id IS NULL
            OR center_id::text = current_setting('app.center_id', true)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS auth_session_center_isolation ON auth_session")
    op.execute("DROP POLICY IF EXISTS audit_event_center_isolation ON audit_event")
    op.execute("DROP POLICY IF EXISTS app_user_center_isolation ON app_user")
    for table in ("auth_session", "audit_event", "app_user"):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
