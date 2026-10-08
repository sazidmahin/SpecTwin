from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SrsDocumentRead(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    pipeline_run_id: UUID | None
    diagram_id: UUID | None
    title: str
    status: str
    content_markdown: str
    content_json: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SrsDocumentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_markdown: str | None = Field(default=None, min_length=1, max_length=500000)
