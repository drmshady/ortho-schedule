"""add clinics (numbered working units) and clinic-scoped appointments

A center may run multiple clinics (rooms/operatories). Appointments may be assigned to a
clinic; a clinic cannot host two overlapping scheduled appointments (a second GiST exclusion
constraint, alongside the per-doctor one). Clinics carry ``center_id`` with an RLS backstop.

Revision ID: 20260622_0007
Revises: 20260622_0006
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260622_0007"
down_revision: str | None = "20260622_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinic",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("center_id", "name", name="uq_clinic_center_name"),
    )
    # Row-level-security backstop (mirrors the other tenant tables).
    op.execute("ALTER TABLE clinic ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY clinic_center_isolation ON clinic
        USING (center_id::text = current_setting('app.center_id', true))
        """
    )

    op.add_column(
        "appointment",
        sa.Column(
            "clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinic.id"), nullable=True
        ),
    )
    # A clinic (room) may not host two overlapping scheduled appointments. NULL clinic_id rows
    # never conflict (GiST treats NULLs as distinct), so unassigned bookings are unaffected.
    op.execute(
        """
        ALTER TABLE appointment
        ADD CONSTRAINT ex_appointment_clinic_no_double_booking
        EXCLUDE USING gist (clinic_id WITH =, period WITH &&)
        WHERE (status = 'scheduled' AND clinic_id IS NOT NULL)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE appointment DROP CONSTRAINT IF EXISTS ex_appointment_clinic_no_double_booking"
    )
    op.drop_column("appointment", "clinic_id")
    op.execute("DROP POLICY IF EXISTS clinic_center_isolation ON clinic")
    op.execute("ALTER TABLE clinic DISABLE ROW LEVEL SECURITY")
    op.drop_table("clinic")
