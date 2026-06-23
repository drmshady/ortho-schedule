from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.user import User


class UserCreate(BaseModel):
    role: str = Field(pattern="^(doctor|reception)$")
    email: str
    display_name: str = Field(min_length=1)
    temp_password: str = Field(min_length=8)
    specialty: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            msg = "email must contain @"
            raise ValueError(msg)
        return value


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    # Grant (True) or revoke (False) center-admin privileges for a doctor/reception user.
    is_admin: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    email: str
    display_name: str
    is_active: bool
    is_admin: bool
    must_change_password: bool

    @classmethod
    def from_model(cls, user: User) -> "UserOut":
        return cls.model_validate(user)
