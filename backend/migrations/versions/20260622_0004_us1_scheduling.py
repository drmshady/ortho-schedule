"""create user-story-1 scheduling tables (doctors, patients, availability, appointments)

Includes the GiST exclusion constraint enforcing no double-booking and per-table
row-level-security backstops mirroring the foundational policies.

Revision ID: 20260622_0004
Revises: 20260622_0003
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260622_0004"
down_revision: str | None = "20260622_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = (
    "doctor_profile",
    "patient",
    "availability_template",
    "availability_exception",
    "appointment",
)


def upgrade() -> None:
    op.create_table(
        "doctor_profile",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("grid_minutes", sa.Integer(), nullable=True),
        sa.Column("specialty", sa.String(length=200), nullable=True),
    )
    op.create_table(
        "patient",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("clinic_identifier", sa.String(length=80), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_patient_center_phone", "patient", ["center_id", "phone"])
    op.create_table(
        "availability_template",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_local", sa.Time(), nullable=False),
        sa.Column("end_local", sa.Time(), nullable=False),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_template_weekday_range"),
        sa.CheckConstraint("end_local > start_local", name="ck_template_time_order"),
    )
    op.create_table(
        "availability_exception",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("start_local", sa.Time(), nullable=True),
        sa.Column("end_local", sa.Time(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
    )
    op.create_table(
        "appointment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        # Maintained by a BEFORE trigger (timestamptz + interval is STABLE, so a generated
        # column is not permitted); backs the no-double-booking exclusion constraint.
        sa.Column("period", postgresql.TSTZRANGE(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("source_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Keep period in sync with starts_at/duration before constraint checks run.
    op.execute(
        """
        CREATE FUNCTION appointment_set_period() RETURNS trigger AS $$
        BEGIN
            NEW.period := tstzrange(
                NEW.starts_at,
                NEW.starts_at + make_interval(mins => NEW.duration_minutes)
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_appointment_set_period
        BEFORE INSERT OR UPDATE OF starts_at, duration_minutes ON appointment
        FOR EACH ROW EXECUTE FUNCTION appointment_set_period()
        """
    )
    # No two scheduled appointments for the same doctor may overlap (Principle IV, FR-020).
    op.execute(
        """
        ALTER TABLE appointment
        ADD CONSTRAINT ex_appointment_no_double_booking
        EXCLUDE USING gist (doctor_id WITH =, period WITH &&)
        WHERE (status = 'scheduled')
        """
    )

    # Row-level-security backstops (mirrors foundational policy form).
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_center_isolation ON {table}
            USING (
                center_id::text = current_setting('app.center_id', true)
            )
            """
        )


def downgrade() -> None:
    for table in _TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_center_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER IF EXISTS trg_appointment_set_period ON appointment")
    op.drop_table("appointment")
    op.execute("DROP FUNCTION IF EXISTS appointment_set_period()")
    op.drop_table("availability_exception")
    op.drop_table("availability_template")
    op.drop_index("ix_patient_center_phone", table_name="patient")
    op.drop_table("patient")
    op.drop_table("doctor_profile")
