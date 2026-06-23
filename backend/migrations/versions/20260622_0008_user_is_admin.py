"""add app_user.is_admin (center-admin privilege grantable to doctor/reception)

A center-admin may grant another staff member (a doctor or reception user) center-admin
privileges while that user keeps their own role. The privilege is a boolean flag on the user;
authorization treats ``role = 'center_admin' OR is_admin`` as having center-admin authority.

Revision ID: 20260622_0008
Revises: 20260622_0007
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_0008"
down_revision: str | None = "20260622_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("app_user", "is_admin")
