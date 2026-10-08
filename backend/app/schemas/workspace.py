from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WorkspaceType = Literal["personal", "organization"]
WorkspaceRole = Literal["owner", "admin", "member", "viewer"]
WorkspaceStatus = Literal["active", "inactive"]


class WorkspaceRead(BaseModel):
    id: UUID
    name: str
    slug: str
    type: WorkspaceType
    owner_user_id: UUID
    status: WorkspaceStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMembershipRead(BaseModel):
    workspace: WorkspaceRead
    role: WorkspaceRole
    status: WorkspaceStatus

    model_config = ConfigDict(from_attributes=True)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=3, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    type: Literal["organization"]


class WorkspaceMemberInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["admin", "member", "viewer"] = "member"


class WorkspaceMemberUserRead(BaseModel):
    id: UUID
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberRoleUpdateRequest(BaseModel):
    role: Literal["admin", "member", "viewer"]


class WorkspaceMemberRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    user: WorkspaceMemberUserRead | None = None
    role: WorkspaceRole
    status: WorkspaceStatus
    invited_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


InvitationStatus = Literal["pending", "accepted", "revoked", "expired"]


class WorkspaceInvitationRead(BaseModel):
    id: UUID
    workspace_id: UUID
    email: str
    role: WorkspaceRole
    status: InvitationStatus
    invited_by: UUID
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceInvitationCreateResponse(WorkspaceInvitationRead):
    # Set only when EMAIL_DELIVERY_MODE=console, so local development can open
    # the link without a mail server.
    invite_url: str | None = None


class WorkspaceInvitationPreview(BaseModel):
    workspace_name: str
    inviter_name: str
    email: str
    role: WorkspaceRole
    status: InvitationStatus
    expires_at: datetime
    account_exists: bool
