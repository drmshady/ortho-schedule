from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.appointment_request import AppointmentRequest
from src.services.request_service import is_overdue


class AppointmentRequestCreate(BaseModel):
    patient_id: UUID
    # Reason / visit type is optional — reception can book without one.
    reason: str | None = None
    preferred_from: date | None = None
    preferred_to: date | None = None
    urgency: str = Field(pattern="^(routine|soon|urgent)$")
    expected_duration_minutes: int = Field(gt=0)
    notes: str | None = None


class RequestDecline(BaseModel):
    decline_reason: str = Field(min_length=1)


class AppointmentRequestOut(BaseModel):
    id: UUID
    doctor_id: UUID
    patient_id: UUID
    reason: str | None = None
    preferred_from: date | None = None
    preferred_to: date | None = None
    urgency: str
    expected_duration_minutes: int
    notes: str | None = None
    status: str
    decline_reason: str | None = None
    is_overdue: bool
    resulting_appointment_id: UUID | None = None

    @classmethod
    def from_model(cls, request: AppointmentRequest) -> "AppointmentRequestOut":
        return cls(
            id=request.id,
            doctor_id=request.doctor_id,
            patient_id=request.patient_id,
            reason=request.reason,
            preferred_from=request.preferred_from,
            preferred_to=request.preferred_to,
            urgency=request.urgency,
            expected_duration_minutes=request.expected_duration_minutes,
            notes=request.notes,
            status=request.status,
            decline_reason=request.decline_reason,
            is_overdue=is_overdue(request),
            resulting_appointment_id=request.resulting_appointment_id,
        )
