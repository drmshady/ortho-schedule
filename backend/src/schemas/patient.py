from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    clinic_identifier: str
    phone: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1)
    # Optional: the clinic's own file/record number. When omitted, the server assigns the
    # next sequential per-center identifier (e.g. "P-0001").
    clinic_identifier: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    confirm_possible_duplicate: bool = False


class DuplicateWarning(BaseModel):
    code: str = "possible_duplicate"
    candidates: list[PatientOut]
