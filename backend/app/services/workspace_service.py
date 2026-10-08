from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import User, Workspace, WorkspaceMember

WORKSPACE_ROLES = {"owner", "admin", "member", "viewer"}
INVITABLE_ROLES = {"admin", "member", "viewer"}
MANAGER_ROLES = {"owner", "admin"}


class WorkspaceError(Exception):
    """Base class for expected workspace failures."""


class DuplicateWorkspaceSlugError(WorkspaceError):
    pass


class DuplicateWorkspaceMemberError(WorkspaceError):
    pass


class InvalidWorkspaceError(WorkspaceError):
    pass


class WorkspaceNotFoundError(WorkspaceError):
    pass


class WorkspacePermissionError(WorkspaceError):
    pass


class UserNotFoundError(WorkspaceError):
    pass


def list_user_workspace_memberships(
    db: Session, *, user_id: UUID
) -> list[WorkspaceMember]:
    return list(
        db.scalars(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.workspace))
            .join(Workspace)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == "active",
                Workspace.status == "active",
            )
            .order_by(Workspace.type.asc(), Workspace.created_at.asc())
        )
    )


def create_organization_workspace(
    db: Session, *, owner: User, name: str, slug: str
) -> WorkspaceMember:
    normalized_name = name.strip()
    normalized_slug = slug.strip().lower()
    if not normalized_name:
        raise InvalidWorkspaceError("Workspace name is required")

    existing = db.scalar(select(Workspace).where(Workspace.slug == normalized_slug))
    if existing is not None:
        raise DuplicateWorkspaceSlugError("Workspace slug is already in use")

    workspace = Workspace(
        name=normalized_name,
        slug=normalized_slug,
        type="organization",
        owner_user_id=owner.id,
        status="active",
    )
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=owner.id,
        role="owner",
        status="active",
    )
    db.add(membership)
    db.commit()

    return get_active_workspace_membership(db, user_id=owner.id, workspace_id=workspace.id)


def get_active_workspace_membership(
    db: Session, *, user_id: UUID, workspace_id: UUID
) -> WorkspaceMember:
    membership = db.scalar(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.workspace))
        .join(Workspace)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == "active",
            Workspace.status == "active",
        )
    )
    if membership is None:
        raise WorkspaceNotFoundError("Workspace not found")
    return membership


def require_workspace_role(
    membership: WorkspaceMember, *, allowed_roles: set[str]
) -> None:
    if membership.role not in allowed_roles:
        raise WorkspacePermissionError("Insufficient workspace permissions")


def list_workspace_members(
    db: Session, *, workspace_id: UUID, requester_membership: WorkspaceMember
) -> list[WorkspaceMember]:
    require_workspace_role(requester_membership, allowed_roles=MANAGER_ROLES)
    return list(
        db.scalars(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.status == "active",
            )
            .order_by(WorkspaceMember.created_at.asc())
        )
    )


def _managed_member(
    db: Session, *, workspace_id: UUID, requester_membership: WorkspaceMember, member_id: UUID
) -> WorkspaceMember:
    require_workspace_role(requester_membership, allowed_roles=MANAGER_ROLES)
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == "active",
        )
    )
    if member is None:
        raise UserNotFoundError("Workspace member not found")
    if member.role == "owner":
        raise InvalidWorkspaceError("The workspace owner cannot be changed or removed")
    return member


def update_workspace_member_role(
    db: Session, *, workspace_id: UUID, requester_membership: WorkspaceMember, member_id: UUID, role: str
) -> WorkspaceMember:
    member = _managed_member(
        db, workspace_id=workspace_id, requester_membership=requester_membership, member_id=member_id
    )
    if role not in INVITABLE_ROLES:
        raise InvalidWorkspaceError("Invalid workspace role")
    member.role = role
    db.commit()
    db.refresh(member)
    return member


def remove_workspace_member(
    db: Session, *, workspace_id: UUID, requester_membership: WorkspaceMember, member_id: UUID
) -> None:
    member = _managed_member(
        db, workspace_id=workspace_id, requester_membership=requester_membership, member_id=member_id
    )
    member.status = "removed"
    db.commit()
