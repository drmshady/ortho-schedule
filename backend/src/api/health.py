from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str] | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": "down"},
        )
    return {"status": "ok", "database": "up"}
