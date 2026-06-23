from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_event import AuditEvent
from src.models.user import User


async def write_audit_event(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: UUID | None,
    center_id: UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        center_id=center_id if center_id is not None else actor.center_id,
        actor_user_id=actor.id,
        actor_role=actor.role,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(event)
    return event
