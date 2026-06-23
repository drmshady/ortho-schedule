import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class AppointmentRequest(Base):
    """A doctor-originated request handed to reception (FR-014..FR-018).

    State machine (each transition audited): ``pending -> fulfilled`` (reception books a slot)
    or ``pending -> declined`` (reception, with reason). Only reception may fulfill/decline.
    "Overdue" is derived (now > ``preferred_to``) for queue highlighting — not stored.
    """

    __tablename__ = "appointment_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("center.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, default="routine")
    expected_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resulting_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
