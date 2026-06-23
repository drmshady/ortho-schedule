from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    patient_id: UUID
    clinic_id: UUID | None = None
    starts_at: datetime
    duration_minutes: int
    status: str
    origin: str
    source_request_id: UUID | None = None


class AppointmentCreate(BaseModel):
    doctor_id: UUID
    # Either reference an existing patient by id, or supply a walk-in patient's name + clinic id
    # (resolved/created on the fly so the patient need not be pre-registered).
    patient_id: UUID | None = None
    patient_name: str | None = None
    patient_clinic_identifier: str | None = None
    clinic_id: UUID | None = None
    starts_at: datetime
    duration_minutes: int = Field(gt=0)
    source_request_id: UUID | None = None
    confirm_patient_conflict: bool = False

    @model_validator(mode="after")
    def _require_patient(self) -> "AppointmentCreate":
        has_walk_in = bool(
            self.patient_name
            and self.patient_name.strip()
            and self.patient_clinic_identifier
            and self.patient_clinic_identifier.strip()
        )
        if self.patient_id is None and not has_walk_in:
            msg = "Provide patient_id or both patient_name and patient_clinic_identifier"
            raise ValueError(msg)
        return self


class AppointmentReschedule(BaseModel):
    starts_at: datetime
    duration_minutes: int = Field(gt=0)
    confirm_patient_conflict: bool = False


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(pattern="^(completed|cancelled|no_show)$")
    cancel_reason: str | None = None
