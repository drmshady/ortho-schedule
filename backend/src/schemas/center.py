from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.center import Center

# Saudi Arabia is the default time zone for new centers.
DEFAULT_TIMEZONE = "Asia/Riyadh"


def _validate_timezone(value: str) -> str:
    value = value.strip()
    if not value:
        msg = "timezone is required"
        raise ValueError(msg)
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        msg = f"Unknown time zone: {value!r}"
        raise ValueError(msg) from exc
    return value


class CenterCreate(BaseModel):
    name: str = Field(min_length=1)
    timezone: str = Field(default=DEFAULT_TIMEZONE, min_length=1)
    grid_minutes: int = Field(default=15, gt=0)
    admin_email: str
    admin_temp_password: str = Field(min_length=8)
    # The first admin can be a dedicated center_admin (default) or a doctor/reception account
    # that is also granted center-admin privileges (is_admin) — see UserManagement.
    admin_role: str = Field(default="center_admin", pattern="^(center_admin|doctor|reception)$")

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return _validate_timezone(value)

    @field_validator("admin_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            msg = "admin_email must contain @"
            raise ValueError(msg)
        return value


class CenterStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")


class CenterUpdate(BaseModel):
    timezone: str = Field(min_length=1)

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return _validate_timezone(value)


class CenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    timezone: str
    grid_minutes: int
    status: str

    @classmethod
    def from_model(cls, center: Center) -> "CenterOut":
        return cls.model_validate(center)
