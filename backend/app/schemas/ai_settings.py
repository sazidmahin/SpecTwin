from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


AiProvider = Literal["openai", "anthropic", "gemini"]


class AiCredentialPutRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=4096)
    selected_model: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class AiCredentialPatchRequest(BaseModel):
    selected_model: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None


class AiCredentialSafeRead(BaseModel):
    id: UUID
    provider: AiProvider
    configured: bool
    key_last_four: str
    selected_model: str
    is_default: bool
    status: str
    validated_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    test_response: str | None = None


class AiProviderSettingRead(BaseModel):
    provider: AiProvider
    label: str
    models: list[str]
    default_model: str
    credential: AiCredentialSafeRead | None

