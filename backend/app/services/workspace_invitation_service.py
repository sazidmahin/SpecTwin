"""Email invitations to organization workspaces.

An owner or admin invites an email address. The invitee gets a link carrying a
random token; whoever signs in with that email (registering first if they have
no account) can accept it and becomes a member with the invited role.
"""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import User, WorkspaceInvitation, WorkspaceMember
from app.services.email_service import send_workspace_invitation
from app.services.workspace_service import (
    INVITABLE_ROLES,
    MANAGER_ROLES,
    DuplicateWorkspaceMemberError,
    InvalidWorkspaceError,
    WorkspaceError,
    get_active_workspace_membership,
    require_workspace_role,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvitationNotFoundError(WorkspaceError):
    pass


class InvitationUnavailableError(WorkspaceError):
    """The invitation was accepted, revoked or has expired."""


class InvitationEmailMismatchError(WorkspaceError):
    pass


@dataclass(frozen=True)
class InvitationCreated:
    invitation: WorkspaceInvitation
    # Only returned when emails are printed to the console (local development),
    # mirroring how the verification code is surfaced in that mode.
    invite_url: str | None


@dataclass(frozen=True)
class InvitationPreview:
    workspace_name: str
    inviter_name: str
    email: str
    role: str
    status: str
    expires_at: datetime
    account_exists: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invite_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/#/invite/{token}"


def _effective_status(invitation: WorkspaceInvitation) -> str:
    if invitation.status == "pending" and _as_aware(invitation.expires_at) < _now():
        return "expired"
    return invitation.status


def invite_to_workspace(
    db: Session,
    *,
    workspace_id: UUID,
    requester_membership: WorkspaceMember,
    email: str,
    role: str,
) -> InvitationCreated:
    require_workspace_role(requester_membership, allowed_roles=MANAGER_ROLES)
    workspace = requester_membership.workspace
    if workspace.type != "organization":
        raise InvalidWorkspaceError("Members can only be invited to organization workspaces")
    if role not in INVITABLE_ROLES:
        raise InvalidWorkspaceError("Invalid workspace role")
    normalized_email = email.strip().lower()
    if not _EMAIL_RE.match(normalized_email):
        raise InvalidWorkspaceError("Invalid email address")

    already_member = db.scalar(
        select(WorkspaceMember)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active",
            User.email == normalized_email,
        )
    )
    if already_member is not None:
        raise DuplicateWorkspaceMemberError("User is already a workspace member")

    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(days=settings.workspace_invitation_expire_days)
    # Inviting the same email again refreshes the pending invitation (new role,
    # new link, new expiry) instead of piling up duplicates.
    invitation = db.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.email == normalized_email,
            WorkspaceInvitation.status == "pending",
        )
    )
    if invitation is None:
        invitation = WorkspaceInvitation(workspace_id=workspace_id, email=normalized_email, status="pending")
        db.add(invitation)
    invitation.role = role
    invitation.token_hash = _hash_token(token)
    invitation.invited_by = requester_membership.user_id
    invitation.expires_at = expires_at
    db.flush()

    inviter = db.get(User, requester_membership.user_id)
    invite_url = _invite_url(token)
    send_workspace_invitation(
        email=normalized_email,
        workspace_name=workspace.name,
        inviter_name=inviter.full_name if inviter else "A teammate",
        role=role,
        invite_url=invite_url,
    )
    db.commit()
    db.refresh(invitation)

    return InvitationCreated(
        invitation=invitation,
        invite_url=invite_url if settings.email_delivery_mode == "console" else None,
    )


def list_pending_invitations(
    db: Session, *, workspace_id: UUID, requester_membership: WorkspaceMember
) -> list[WorkspaceInvitation]:
    require_workspace_role(requester_membership, allowed_roles=MANAGER_ROLES)
    invitations = db.scalars(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.status == "pending",
        )
        .order_by(WorkspaceInvitation.created_at.asc())
    )
    return [invitation for invitation in invitations if _effective_status(invitation) == "pending"]


def revoke_invitation(
    db: Session, *, workspace_id: UUID, requester_membership: WorkspaceMember, invitation_id: UUID
) -> None:
    require_workspace_role(requester_membership, allowed_roles=MANAGER_ROLES)
    invitation = db.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.status == "pending",
        )
    )
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found")
    invitation.status = "revoked"
    db.commit()


def _invitation_by_token(db: Session, token: str) -> WorkspaceInvitation:
    invitation = db.scalar(
        select(WorkspaceInvitation)
        .options(selectinload(WorkspaceInvitation.workspace), selectinload(WorkspaceInvitation.inviter))
        .where(WorkspaceInvitation.token_hash == _hash_token(token))
    )
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found")
    return invitation


def preview_invitation(db: Session, *, token: str) -> InvitationPreview:
    invitation = _invitation_by_token(db, token)
    status = _effective_status(invitation)
    if status == "pending" and invitation.workspace.status != "active":
        status = "revoked"
    account_exists = db.scalar(select(User.id).where(User.email == invitation.email)) is not None
    return InvitationPreview(
        workspace_name=invitation.workspace.name,
        inviter_name=invitation.inviter.full_name,
        email=invitation.email,
        role=invitation.role,
        status=status,
        expires_at=invitation.expires_at,
        account_exists=account_exists,
    )


def accept_invitation(db: Session, *, token: str, user: User) -> WorkspaceMember:
    invitation = _invitation_by_token(db, token)
    status = _effective_status(invitation)
    if status == "accepted":
        raise InvitationUnavailableError("This invitation has already been used")
    if status == "expired":
        raise InvitationUnavailableError("This invitation has expired. Ask for a new one.")
    if status != "pending" or invitation.workspace.status != "active":
        raise InvitationUnavailableError("This invitation is no longer valid")
    if user.email.strip().lower() != invitation.email:
        raise InvitationEmailMismatchError(
            f"This invitation was sent to {invitation.email}. Sign in with that email to accept it."
        )

    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        db.add(
            WorkspaceMember(
                workspace_id=invitation.workspace_id,
                user_id=user.id,
                role=invitation.role,
                status="active",
                invited_by=invitation.invited_by,
            )
        )
    elif membership.status != "active":
        # Someone removed earlier and invited back.
        membership.status = "active"
        membership.role = invitation.role
        membership.invited_by = invitation.invited_by

    invitation.status = "accepted"
    invitation.accepted_by = user.id
    invitation.accepted_at = _now()
    db.commit()

    return get_active_workspace_membership(db, user_id=user.id, workspace_id=invitation.workspace_id)
