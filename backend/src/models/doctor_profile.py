import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class DoctorProfile(Base):
    """Scheduling attributes for a ``doctor``-role user (1:1 with User)."""

    __tablename__ = "doctor_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True
    )
    center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("center.id"), nullable=False
    )
    grid_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(200), nullable=True)
