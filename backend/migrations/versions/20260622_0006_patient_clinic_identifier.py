"""identify patients by clinic identifier instead of phone

Patients are now entered with a name and a clinic identifier (ID); phone becomes optional.
Makes ``clinic_identifier`` NOT NULL, ``phone`` nullable, and swaps the lookup index.

Revision ID: 20260622_0006
Revises: 20260622_0005
Create Date: 2026-06-22
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260622_0006"
down_revision: str | None = "20260622_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_patient_center_phone", table_name="patient")
    # Backfill any rows missing an identifier before enforcing NOT NULL.
    op.execute("UPDATE patient SET clinic_identifier = id::text WHERE clinic_identifier IS NULL")
    op.alter_column("patient", "clinic_identifier", nullable=False)
    op.alter_column("patient", "phone", nullable=True)
    op.create_index("ix_patient_center_clinic_id", "patient", ["center_id", "clinic_identifier"])


def downgrade() -> None:
    op.drop_index("ix_patient_center_clinic_id", table_name="patient")
    op.execute("UPDATE patient SET phone = '' WHERE phone IS NULL")
    op.alter_column("patient", "phone", nullable=False)
    op.alter_column("patient", "clinic_identifier", nullable=True)
    op.create_index("ix_patient_center_phone", "patient", ["center_id", "phone"])
