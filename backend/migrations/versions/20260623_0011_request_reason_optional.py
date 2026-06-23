"""make appointment_request.reason optional

A doctor's appointment request no longer requires a reason / visit type; reception can book
without one. The column becomes nullable.

Revision ID: 20260623_0011
Revises: 20260623_0010
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0011"
down_revision: str | None = "20260623_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("appointment_request", "reason", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE appointment_request SET reason = '' WHERE reason IS NULL")
    op.alter_column("appointment_request", "reason", existing_type=sa.Text(), nullable=False)
