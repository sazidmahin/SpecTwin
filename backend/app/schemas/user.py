from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: str
    avatar_url: str | None = None
    status: str
    email_verified: bool = True
    email_verified_at: datetime | None = None
    platform_role: str = "user"
    is_platform_admin: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
