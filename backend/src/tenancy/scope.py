from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.core.session import CurrentSession, current_session


@dataclass(frozen=True)
class CenterScope:
    center_id: UUID
    user_id: UUID
    role: str
    is_admin: bool = False

    def require_admin(self) -> None:
        """Gate center-admin actions. A user holds center-admin authority if their role is
        ``center_admin`` or they have been granted the ``is_admin`` privilege on top of their
        doctor/reception role."""
        if self.role != "center_admin" and not self.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "Center-admin privileges are required"},
            )

    def require_same_center(self, center_id: UUID | None) -> None:
        if center_id != self.center_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": "Resource is outside the current center scope",
                },
            )

    def require_role(self, *roles: str) -> None:
        if self.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "Role is not permitted for this action"},
            )


async def center_scope(session: CurrentSession = Depends(current_session)) -> CenterScope:
    if session.user.center_id is None or session.center is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Center scope is required"},
        )
    return CenterScope(
        center_id=session.user.center_id,
        user_id=session.user.id,
        role=session.user.role,
        is_admin=session.user.is_admin,
    )


async def require_password_changed(
    session: CurrentSession = Depends(current_session),
) -> CurrentSession:
    if session.user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "password_change_required", "message": "Password change required"},
        )
    return session


async def require_super_admin(
    session: CurrentSession = Depends(require_password_changed),
) -> CurrentSession:
    """Gate platform-wide (cross-center) endpoints to the super-admin role (US4)."""
    if session.user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Super-admin role required"},
        )
    return session
