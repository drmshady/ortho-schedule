"""In-app notifications (FR-017, FR-026).

Notifications are written transactionally with the event that triggers them (the caller owns
the commit). Payloads carry references (ids) only — never patient-identifying text — keeping
PHI out of notification storage (Principle I).
"""
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notification import Notification
from src.tenancy.scope import CenterScope


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def write(
        self,
        *,
        center_id: UUID,
        recipient_user_id: UUID,
        type: str,
        payload: dict[str, Any],
    ) -> Notification:
        """Add a notification to the current transaction (caller commits)."""
        notification = Notification(
            center_id=center_id,
            recipient_user_id=recipient_user_id,
            type=type,
            payload=payload,
            is_read=False,
        )
        self.db.add(notification)
        return notification

    async def list_for_recipient(
        self, *, scope: CenterScope, recipient_user_id: UUID, unread_only: bool = False
    ) -> list[Notification]:
        stmt = select(Notification).where(
            Notification.center_id == scope.center_id,
            Notification.recipient_user_id == recipient_user_id,
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def mark_read(
        self, *, scope: CenterScope, recipient_user_id: UUID, notification_id: UUID
    ) -> None:
        notification = await self.db.get(Notification, notification_id)
        if (
            notification is None
            or notification.center_id != scope.center_id
            or notification.recipient_user_id != recipient_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Notification not found"},
            )
        notification.is_read = True
        await self.db.commit()
