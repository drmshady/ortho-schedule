"""add availability_template.clinic_id (assign a doctor to a clinic per session)

A doctor's recurring working-hours session may be assigned to a specific clinic (working
unit). The column is nullable: null means no specific clinic for that session.

Revision ID: 20260623_0009
Revises: 20260622_0008
Create Date: 2026-06-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0009"
down_revision: str | None = "20260622_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "availability_template",
        sa.Column("clinic_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_availability_template_clinic_id",
        "availability_template",
        "clinic",
        ["clinic_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_availability_template_clinic_id", "availability_template", type_="foreignkey"
    )
    op.drop_column("availability_template", "clinic_id")
