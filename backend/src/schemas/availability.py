from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityTemplateCreate(BaseModel):
    doctor_id: UUID
    clinic_id: UUID | None = None
    weekday: int = Field(ge=0, le=6)
    start_local: time
    end_local: time


class AvailabilityTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    clinic_id: UUID | None = None
    weekday: int
    start_local: time
    end_local: time


class AvailabilityExceptionCreate(BaseModel):
    doctor_id: UUID
    clinic_id: UUID | None = None
    date: date
    kind: str = Field(pattern="^(block|override|extra)$")
    start_local: time | None = None
    end_local: time | None = None
    reason: str | None = None


class AvailabilityExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    clinic_id: UUID | None = None
    date: date
    kind: str
    start_local: time | None = None
    end_local: time | None = None
    reason: str | None = None


class BookableInterval(BaseModel):
    start: datetime
    end: datetime


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    email: str
    display_name: str
    is_active: bool
    must_change_password: bool
