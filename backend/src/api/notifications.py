from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.session import CurrentSession
from src.schemas.notification import NotificationOut
from src.services.notification_service import NotificationService
from src.tenancy.scope import CenterScope, center_scope, require_password_changed

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread: bool | None = None,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    notifications = await NotificationService(db).list_for_recipient(
        scope=scope,
        recipient_user_id=session.user.id,
        unread_only=bool(unread),
    )
    return [NotificationOut.model_validate(n) for n in notifications]


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: UUID,
    session: CurrentSession = Depends(require_password_changed),
    scope: CenterScope = Depends(center_scope),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await NotificationService(db).mark_read(
        scope=scope,
        recipient_user_id=session.user.id,
        notification_id=notification_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
