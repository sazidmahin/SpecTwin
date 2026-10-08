from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace_membership, get_db
from app.db.models import User, WorkspaceInvitation, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceInvitationCreateResponse,
    WorkspaceInvitationRead,
    WorkspaceMemberInviteRequest,
    WorkspaceMemberRead,
    WorkspaceMemberRoleUpdateRequest,
    WorkspaceMembershipRead,
)
from app.services.email_service import EmailDeliveryError
from app.services.workspace_invitation_service import (
    InvitationNotFoundError,
    invite_to_workspace,
    list_pending_invitations,
    revoke_invitation,
)
from app.services.workspace_service import (
    DuplicateWorkspaceMemberError,
    DuplicateWorkspaceSlugError,
    InvalidWorkspaceError,
    UserNotFoundError,
    WorkspacePermissionError,
    create_organization_workspace,
    list_user_workspace_memberships,
    list_workspace_members,
    remove_workspace_member,
    update_workspace_member_role,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceMembershipRead])
def list_workspaces(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WorkspaceMember]:
    return list_user_workspace_memberships(db, user_id=user.id)


@router.post(
    "",
    response_model=WorkspaceMembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    payload: WorkspaceCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceMember:
    try:
        return create_organization_workspace(
            db, owner=user, name=payload.name, slug=payload.slug
        )
    except DuplicateWorkspaceSlugError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidWorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/{workspace_id}", response_model=WorkspaceMembershipRead)
def get_workspace(
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
) -> WorkspaceMember:
    return membership


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
def get_members(
    workspace_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[WorkspaceMember]:
    try:
        return list_workspace_members(
            db, workspace_id=workspace_id, requester_membership=membership
        )
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/{workspace_id}/members/invite",
    response_model=WorkspaceInvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    workspace_id: UUID,
    payload: WorkspaceMemberInviteRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> WorkspaceInvitationCreateResponse:
    try:
        result = invite_to_workspace(
            db,
            workspace_id=workspace_id,
            requester_membership=membership,
            email=payload.email,
            role=payload.role,
        )
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DuplicateWorkspaceMemberError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidWorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the invitation email. Please try again later.",
        ) from exc

    response = WorkspaceInvitationCreateResponse.model_validate(result.invitation)
    response.invite_url = result.invite_url
    return response


@router.get("/{workspace_id}/invitations", response_model=list[WorkspaceInvitationRead])
def get_invitations(
    workspace_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[WorkspaceInvitation]:
    try:
        return list_pending_invitations(db, workspace_id=workspace_id, requester_membership=membership)
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete("/{workspace_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invitation(
    workspace_id: UUID,
    invitation_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        revoke_invitation(
            db, workspace_id=workspace_id, requester_membership=membership, invitation_id=invitation_id
        )
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvitationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberRead)
def update_member_role(
    workspace_id: UUID,
    member_id: UUID,
    payload: WorkspaceMemberRoleUpdateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> WorkspaceMember:
    try:
        return update_workspace_member_role(
            db, workspace_id=workspace_id, requester_membership=membership, member_id=member_id, role=payload.role
        )
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidWorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.delete("/{workspace_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: UUID,
    member_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        remove_workspace_member(db, workspace_id=workspace_id, requester_membership=membership, member_id=member_id)
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidWorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
