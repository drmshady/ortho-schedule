from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClinicCreate(BaseModel):
    # Working units are named by number/label, e.g. "1", "2", "Room A".
    name: str = Field(min_length=1, max_length=80)


class ClinicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None


class ClinicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_active: bool
