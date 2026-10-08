from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


GenerationMode = Literal["rule_based", "srsgen", "byok", "ollama", "ai"]
PipelineStage = Literal["input", "clarifications", "final-story", "requirements", "class-model", "xml"]


class PipelineRunCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    raw_text: str = Field(min_length=1, max_length=200000)
    generation_mode: GenerationMode


class PipelineRunUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class PipelineStageRevisionCreateRequest(BaseModel):
    payload: dict[str, Any]
    expected_version: int | None = Field(default=None, ge=1)


class PipelineStageApproveRequest(BaseModel):
    version_number: int = Field(ge=1)
    proceed: bool = True


class PipelineClassMutationRequest(BaseModel):
    data: dict[str, Any]
    expected_version: int | None = Field(default=None, ge=1)


class PipelineStageRevisionRead(BaseModel):
    id: UUID
    stage_name: str
    version_number: int
    status: str
    payload: dict[str, Any]
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PipelineRunRead(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    title: str
    raw_text: str
    generation_mode: GenerationMode
    provider: str | None
    model_name: str | None
    current_stage: str
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    srs_document_id: UUID | None = None
    stages: list[PipelineStageRevisionRead]


class PipelineRunSummaryRead(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    project_name: str | None
    title: str
    generation_mode: GenerationMode
    provider: str | None
    model_name: str | None
    current_stage: str
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    srs_document_id: UUID | None = None

