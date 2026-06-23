"""create user-story-2 tables (appointment requests, notifications)

Adds the doctor->reception request handoff and in-app notifications, with per-table
row-level-security backstops mirroring the foundational policies.

Revision ID: 20260622_0005
Revises: 20260622_0004
Create Date: 2026-06-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260622_0005"
down_revision: str | None = "20260622_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = ("appointment_request", "notification")


def upgrade() -> None:
    op.create_table(
        "appointment_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("preferred_from", sa.Date(), nullable=True),
        sa.Column("preferred_to", sa.Date(), nullable=True),
        sa.Column("urgency", sa.String(length=20), nullable=False),
        sa.Column("expected_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("resulting_appointment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "urgency IN ('routine', 'soon', 'urgent')", name="ck_request_urgency"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'fulfilled', 'declined')", name="ck_request_status"
        ),
    )
    op.create_index(
        "ix_request_center_status", "appointment_request", ["center_id", "status"]
    )
    op.create_table(
        "notification",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("center.id"), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_notification_recipient_unread",
        "notification",
        ["recipient_user_id", "is_read"],
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
    op.drop_index("ix_notification_recipient_unread", table_name="notification")
    op.drop_table("notification")
    op.drop_index("ix_request_center_status", table_name="appointment_request")
    op.drop_table("appointment_request")
