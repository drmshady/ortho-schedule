"""add availability_exception.clinic_id (per-date session clinic assignment)

A date-specific availability session may be assigned to a specific clinic (working unit),
supporting week-by-week schedules that differ from the recurring weekly template. Nullable:
null means no specific clinic for that session.

Revision ID: 20260623_0010
Revises: 20260623_0009
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0010"
down_revision: str | None = "20260623_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "availability_exception",
        sa.Column("clinic_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_availability_exception_clinic_id",
        "availability_exception",
        "clinic",
        ["clinic_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_availability_exception_clinic_id", "availability_exception", type_="foreignkey"
    )
    op.drop_column("availability_exception", "clinic_id")
