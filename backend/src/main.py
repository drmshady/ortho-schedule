import logging
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from src.api.appointments import router as appointments_router
from src.api.auth import router as auth_router
from src.api.availability import router as availability_router
from src.api.centers import router as centers_router
from src.api.clinics import router as clinics_router
from src.api.health import router as health_router
from src.api.notifications import router as notifications_router
from src.api.patients import router as patients_router
from src.api.requests import router as requests_router
from src.api.users import router as users_router
from src.schemas.common import Error
from src.tenancy.scope import center_scope, require_password_changed

PHI_KEYS = {"full_name", "phone", "clinic_identifier", "date_of_birth", "notes", "reason"}


class PhiRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for key in PHI_KEYS:
            message = message.replace(key, "[redacted]")
        record.msg = message
        record.args = ()
        return True


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return response


def create_app() -> FastAPI:
    logging.getLogger().addFilter(PhiRedactionFilter())
    app = FastAPI(title="Clinic Patient Scheduling API")
    app.middleware("http")(security_headers_middleware)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and {"code", "message"} <= set(exc.detail):
            content = Error(**exc.detail).model_dump()
        else:
            content = Error(code="http_error", message=str(exc.detail)).model_dump()
        return JSONResponse(status_code=exc.status_code, content=content)

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(patients_router, prefix="/api/v1")
    app.include_router(availability_router, prefix="/api/v1")
    app.include_router(appointments_router, prefix="/api/v1")
    app.include_router(requests_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(centers_router, prefix="/api/v1")
    app.include_router(clinics_router, prefix="/api/v1")

    @app.get(
        "/api/v1/_scope-check",
        dependencies=[Depends(require_password_changed), Depends(center_scope)],
        include_in_schema=False,
    )
    async def scope_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
