from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.patient import DuplicateWarning, PatientCreate, PatientOut
from src.services.patient_service import PatientService
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut])
async def search_patients(
    q: str | None = None,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[PatientOut]:
    scope.require_role("reception", "center_admin", "doctor")
    service = PatientService(db)
    patients = await service.search(scope, session.user, q)
    await db.commit()
    return [PatientOut.model_validate(p) for p in patients]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PatientOut)
async def create_patient(
    payload: PatientCreate,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> Response:
    scope.require_role("reception", "center_admin")
    service = PatientService(db)
    if not payload.confirm_possible_duplicate:
        duplicates = await service.find_duplicates(
            scope, payload.full_name, payload.clinic_identifier
        )
        if duplicates:
            candidates = [PatientOut.model_validate(p) for p in duplicates]
            warning = DuplicateWarning(candidates=candidates)
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT, content=warning.model_dump(mode="json")
            )
    clinic_identifier = (payload.clinic_identifier or "").strip()
    if not clinic_identifier:
        clinic_identifier = await service.next_clinic_identifier(scope)
    patient = await service.create(
        scope,
        session.user,
        full_name=payload.full_name,
        phone=payload.phone,
        clinic_identifier=clinic_identifier,
        date_of_birth=payload.date_of_birth,
        notes=payload.notes,
    )
    await db.commit()
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=PatientOut.model_validate(patient).model_dump(mode="json"),
    )
