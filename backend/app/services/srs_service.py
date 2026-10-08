"""SRS documents: published from completed generation pipeline runs, then read, edited and exported."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Diagram,
    DiagramVersion,
    GenerationPipelineRun,
    GenerationStageRevision,
    Project,
    SrsDocument,
    WorkspaceMember,
)
from app.services.project_service import ProjectNotFoundError, get_active_project
from app.services.srs_document_builder import build_srs_document
from app.services.workspace_service import require_workspace_role

SRS_MUTATION_ROLES = {"owner", "admin", "member"}
ACTIVE_STATUS = "active"
ARCHIVED_STATUS = "archived"


class SrsError(Exception):
    """Base class for expected SRS failures."""


class SrsDocumentNotFoundError(SrsError):
    pass


class InvalidSrsRequestError(SrsError):
    pass


def _ensure_project_access(db: Session, *, membership: WorkspaceMember, project_id: UUID) -> Project:
    try:
        return get_active_project(db, workspace_id=membership.workspace_id, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise SrsDocumentNotFoundError("Project not found") from exc


def list_srs_documents(db: Session, *, membership: WorkspaceMember, project_id: UUID) -> list[SrsDocument]:
    _ensure_project_access(db, membership=membership, project_id=project_id)
    return list(
        db.scalars(
            select(SrsDocument)
            .where(
                SrsDocument.workspace_id == membership.workspace_id,
                SrsDocument.project_id == project_id,
                SrsDocument.status == ACTIVE_STATUS,
            )
            .order_by(SrsDocument.updated_at.desc())
        )
    )


def list_workspace_srs_documents(db: Session, *, membership: WorkspaceMember) -> list[SrsDocument]:
    """Every active SRS document in the workspace whose project is still active."""
    return list(
        db.scalars(
            select(SrsDocument)
            .join(Project, Project.id == SrsDocument.project_id)
            .where(
                SrsDocument.workspace_id == membership.workspace_id,
                SrsDocument.status == ACTIVE_STATUS,
                Project.status == "active",
            )
            .order_by(SrsDocument.updated_at.desc())
        )
    )


def get_srs_document(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, srs_document_id: UUID
) -> SrsDocument:
    _ensure_project_access(db, membership=membership, project_id=project_id)
    document = db.scalar(
        select(SrsDocument).where(
            SrsDocument.id == srs_document_id,
            SrsDocument.workspace_id == membership.workspace_id,
            SrsDocument.project_id == project_id,
            SrsDocument.status == ACTIVE_STATUS,
        )
    )
    if document is None:
        raise SrsDocumentNotFoundError("SRS document not found")
    return document


def update_srs_document(
    db: Session,
    *,
    membership: WorkspaceMember,
    project_id: UUID,
    srs_document_id: UUID,
    title: str | None,
    content_markdown: str | None,
) -> SrsDocument:
    require_workspace_role(membership, allowed_roles=SRS_MUTATION_ROLES)
    document = get_srs_document(db, membership=membership, project_id=project_id, srs_document_id=srs_document_id)
    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise InvalidSrsRequestError("Document title is required")
        document.title = cleaned
    if content_markdown is not None:
        if not content_markdown.strip():
            raise InvalidSrsRequestError("Document content cannot be empty")
        document.content_markdown = content_markdown
        document.content_json = {**(document.content_json or {}), "editedManually": True}
    db.commit()
    db.refresh(document)
    return document


def archive_srs_document(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, srs_document_id: UUID
) -> None:
    require_workspace_role(membership, allowed_roles=SRS_MUTATION_ROLES)
    document = get_srs_document(db, membership=membership, project_id=project_id, srs_document_id=srs_document_id)
    document.status = ARCHIVED_STATUS
    db.commit()


def _latest_stage_payloads(db: Session, run: GenerationPipelineRun) -> tuple[dict[str, dict], dict[str, int]]:
    revisions = db.scalars(
        select(GenerationStageRevision)
        .where(GenerationStageRevision.run_id == run.id)
        .order_by(GenerationStageRevision.version_number.desc())
    ).all()
    payloads: dict[str, dict] = {}
    versions: dict[str, int] = {}
    for revision in revisions:
        if revision.stage_name not in payloads:
            payloads[revision.stage_name] = revision.payload or {}
            versions[revision.stage_name] = revision.version_number
    return payloads, versions


def _publish_diagram(
    db: Session, *, run: GenerationPipelineRun, existing_id: UUID | None, xml: str, user_id: UUID
) -> Diagram:
    diagram = db.get(Diagram, existing_id) if existing_id else None
    if diagram is None or diagram.status != "active":
        diagram = Diagram(
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            title=f"{run.title} — class diagram"[:255],
            diagram_type="class",
            source="generated",
            status="active",
            current_version=1,
            created_by_user_id=user_id,
        )
        db.add(diagram)
        db.flush()
        db.add(
            DiagramVersion(
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                diagram_id=diagram.id,
                version_number=1,
                drawio_xml=xml,
                created_by_user_id=user_id,
            )
        )
        return diagram
    current = db.scalar(
        select(DiagramVersion).where(
            DiagramVersion.diagram_id == diagram.id, DiagramVersion.version_number == diagram.current_version
        )
    )
    if current is None or current.drawio_xml != xml:
        diagram.current_version += 1
        db.add(
            DiagramVersion(
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                diagram_id=diagram.id,
                version_number=diagram.current_version,
                drawio_xml=xml,
                created_by_user_id=user_id,
            )
        )
    return diagram


def publish_pipeline_run(db: Session, *, run: GenerationPipelineRun, user_id: UUID) -> SrsDocument:
    """Create (or refresh, after a reopened stage is re-approved) the SRS document and class diagram for a run."""
    project = db.get(Project, run.project_id)
    payloads, versions = _latest_stage_payloads(db, run)
    document = db.scalar(select(SrsDocument).where(SrsDocument.pipeline_run_id == run.id))

    diagram: Diagram | None = None
    xml = payloads.get("xml", {}).get("xml")
    if isinstance(xml, str) and xml.strip():
        diagram = _publish_diagram(
            db, run=run, existing_id=document.diagram_id if document else None, xml=xml, user_id=user_id
        )

    markdown, content_json = build_srs_document(
        title=run.title,
        project_name=project.name if project else "Project",
        generation_mode=run.generation_mode,
        provider=run.provider,
        model_name=run.model_name,
        raw_text=str(payloads.get("input", {}).get("normalization", {}).get("rawText") or run.raw_text),
        stages=payloads,
        generated_at=datetime.now(UTC),
        diagram_title=diagram.title if diagram else None,
    )
    content_json["stageVersions"] = versions

    if document is None:
        document = SrsDocument(
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            pipeline_run_id=run.id,
            title=run.title,
            status=ACTIVE_STATUS,
            content_markdown=markdown,
            content_json=content_json,
            created_by_user_id=user_id,
        )
        db.add(document)
    else:
        document.content_markdown = markdown
        document.content_json = content_json
        document.status = ACTIVE_STATUS
    db.flush()
    document.diagram_id = diagram.id if diagram else None
    db.commit()
    db.refresh(document)
    return document
