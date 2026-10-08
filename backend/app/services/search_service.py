"""Workspace-wide search across projects, SRS documents, generation runs and diagrams."""

import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Diagram, GenerationPipelineRun, Project, SrsDocument, WorkspaceMember

MAX_QUERY_LENGTH = 200


def _snippet(text: str | None, needle: str, width: int = 90) -> str | None:
    if not text:
        return None
    flat = " ".join(re.sub(r"[#*_`>|]+", " ", text).split())
    index = flat.lower().find(needle.lower())
    if index < 0:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, index - width // 3)
    end = min(len(flat), start + width)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


def search_workspace(db: Session, *, membership: WorkspaceMember, query: str, limit: int = 8) -> dict[str, list[dict[str, Any]]]:
    needle = query.strip()[:MAX_QUERY_LENGTH]
    empty: dict[str, list[dict[str, Any]]] = {"projects": [], "documents": [], "runs": [], "diagrams": []}
    if len(needle) < 2:
        return empty
    pattern = f"%{needle.lower()}%"
    workspace_id = membership.workspace_id

    projects = db.scalars(
        select(Project)
        .where(
            Project.workspace_id == workspace_id,
            Project.status == "active",
            or_(func.lower(Project.name).like(pattern), func.lower(func.coalesce(Project.description, "")).like(pattern)),
        )
        .order_by(Project.updated_at.desc())
        .limit(limit)
    ).all()

    documents = db.execute(
        select(SrsDocument, Project.name)
        .join(Project, Project.id == SrsDocument.project_id)
        .where(
            SrsDocument.workspace_id == workspace_id,
            SrsDocument.status == "active",
            Project.status == "active",
            or_(func.lower(SrsDocument.title).like(pattern), func.lower(SrsDocument.content_markdown).like(pattern)),
        )
        .order_by(SrsDocument.updated_at.desc())
        .limit(limit)
    ).all()

    runs = db.execute(
        select(GenerationPipelineRun, Project.name)
        .join(Project, Project.id == GenerationPipelineRun.project_id)
        .where(
            GenerationPipelineRun.workspace_id == workspace_id,
            Project.status == "active",
            or_(
                func.lower(GenerationPipelineRun.title).like(pattern),
                func.lower(GenerationPipelineRun.raw_text).like(pattern),
            ),
        )
        .order_by(GenerationPipelineRun.updated_at.desc())
        .limit(limit)
    ).all()

    diagrams = db.execute(
        select(Diagram, Project.name)
        .join(Project, Project.id == Diagram.project_id)
        .where(
            Diagram.workspace_id == workspace_id,
            Diagram.status == "active",
            Project.status == "active",
            func.lower(Diagram.title).like(pattern),
        )
        .order_by(Diagram.updated_at.desc())
        .limit(limit)
    ).all()

    return {
        "projects": [
            {"id": project.id, "project_id": project.id, "title": project.name, "subtitle": _snippet(project.description, needle)}
            for project in projects
        ],
        "documents": [
            {
                "id": document.id,
                "project_id": document.project_id,
                "title": document.title,
                "subtitle": f"{project_name} · {_snippet(document.content_markdown, needle, 70)}",
            }
            for document, project_name in documents
        ],
        "runs": [
            {
                "id": run.id,
                "project_id": run.project_id,
                "title": run.title,
                "subtitle": f"{project_name} · {run.status.replace('_', ' ')}",
            }
            for run, project_name in runs
        ],
        "diagrams": [
            {"id": diagram.id, "project_id": diagram.project_id, "title": diagram.title, "subtitle": project_name}
            for diagram, project_name in diagrams
        ],
    }
