import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class AvailabilityTemplate(Base):
    """Recurring weekly bookable hours for a doctor, authored in center-local time."""

    __tablename__ = "availability_template"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_template_weekday_range"),
        CheckConstraint("end_local > start_local", name="ck_template_time_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("center.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    # Optional working unit the doctor is assigned to for this session (null = no specific clinic).
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinic.id"), nullable=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_local: Mapped[time] = mapped_column(Time, nullable=False)
    end_local: Mapped[time] = mapped_column(Time, nullable=False)
