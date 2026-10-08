from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User, WorkspaceMember
from app.db.session import SessionLocal
from app.services.auth_service import get_user_by_id
from app.services.workspace_service import (
    WorkspaceNotFoundError,
    WorkspacePermissionError,
    get_active_workspace_membership,
    require_workspace_role,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for the duration of a request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = credentials.credentials
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.platform_role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform super admin access required",
        )
    return user


def get_current_workspace_membership(
    workspace_id: Annotated[UUID, Path()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceMember:
    try:
        return get_active_workspace_membership(db, user_id=user.id, workspace_id=workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


def require_workspace_roles(*allowed_roles: str):
    def dependency(
        membership: WorkspaceMember = Depends(get_current_workspace_membership),
    ) -> WorkspaceMember:
        try:
            require_workspace_role(membership, allowed_roles=set(allowed_roles))
        except WorkspacePermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return membership

    return dependency
