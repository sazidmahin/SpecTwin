from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DiagramSource = Literal["manual", "generated"]
DiagramStatus = Literal["active", "archived"]


class DiagramCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    diagram_type: str = Field(default="drawio", min_length=1, max_length=64)
    drawio_xml: str = Field(min_length=1)
    diagram_json: str | None = None


class DiagramUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class DiagramVersionCreateRequest(BaseModel):
    drawio_xml: str = Field(min_length=1)
    diagram_json: str | None = None


class DiagramRead(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    title: str
    diagram_type: str
    source: DiagramSource
    status: DiagramStatus
    current_version: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagramVersionRead(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    diagram_id: UUID
    version_number: int
    drawio_xml: str
    diagram_json: str | None
    created_by_user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagramDetailRead(DiagramRead):
    current: DiagramVersionRead
