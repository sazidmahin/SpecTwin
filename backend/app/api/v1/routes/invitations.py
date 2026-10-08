from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User, WorkspaceMember
from app.schemas.workspace import WorkspaceInvitationPreview, WorkspaceMembershipRead
from app.services.workspace_invitation_service import (
    InvitationEmailMismatchError,
    InvitationNotFoundError,
    InvitationUnavailableError,
    accept_invitation,
    preview_invitation,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("/{token}", response_model=WorkspaceInvitationPreview)
def get_invitation(token: str, db: Session = Depends(get_db)) -> WorkspaceInvitationPreview:
    """Public: the invite page shows what the link is for before the invitee signs in."""
    try:
        preview = preview_invitation(db, token=token)
    except InvitationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return WorkspaceInvitationPreview.model_validate(preview, from_attributes=True)


@router.post("/{token}/accept", response_model=WorkspaceMembershipRead)
def accept(
    token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WorkspaceMember:
    try:
        return accept_invitation(db, token=token, user=user)
    except InvitationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvitationEmailMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvitationUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
