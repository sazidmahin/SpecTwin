from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Diagram, DiagramVersion, Project, WorkspaceMember
from app.services.project_service import ProjectNotFoundError, get_active_project
from app.services.workspace_service import require_workspace_role

DIAGRAM_MUTATION_ROLES = {"owner", "admin", "member"}
ACTIVE_DIAGRAM_STATUS = "active"
ARCHIVED_DIAGRAM_STATUS = "archived"
MANUAL_DIAGRAM_SOURCE = "manual"
GENERATED_DIAGRAM_SOURCE = "generated"


class DiagramError(Exception):
    """Base class for expected diagram failures."""


class DiagramNotFoundError(DiagramError):
    pass


class InvalidDiagramError(DiagramError):
    pass


def _clean_required(value: str, message: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidDiagramError(message)
    return cleaned


def _ensure_project_access(
    db: Session, *, membership: WorkspaceMember, project_id: UUID
) -> None:
    try:
        get_active_project(db, workspace_id=membership.workspace_id, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise DiagramNotFoundError("Project not found") from exc


def create_manual_diagram(
    db: Session,
    *,
    membership: WorkspaceMember,
    project_id: UUID,
    title: str,
    diagram_type: str,
    drawio_xml: str,
    diagram_json: str | None,
    source: str = MANUAL_DIAGRAM_SOURCE,
) -> Diagram:
    require_workspace_role(membership, allowed_roles=DIAGRAM_MUTATION_ROLES)
    _ensure_project_access(db, membership=membership, project_id=project_id)

    diagram = Diagram(
        workspace_id=membership.workspace_id,
        project_id=project_id,
        title=_clean_required(title, "Diagram title is required"),
        diagram_type=_clean_required(diagram_type, "Diagram type is required"),
        source=source,
        status=ACTIVE_DIAGRAM_STATUS,
        current_version=1,
        created_by_user_id=membership.user_id,
    )
    db.add(diagram)
    db.flush()

    version = DiagramVersion(
        workspace_id=membership.workspace_id,
        project_id=project_id,
        diagram_id=diagram.id,
        version_number=1,
        drawio_xml=_clean_required(drawio_xml, "Draw.io XML is required"),
        diagram_json=diagram_json,
        created_by_user_id=membership.user_id,
    )
    db.add(version)
    db.commit()
    db.refresh(diagram)
    return diagram


def list_active_diagrams(
    db: Session, *, membership: WorkspaceMember, project_id: UUID
) -> list[Diagram]:
    _ensure_project_access(db, membership=membership, project_id=project_id)
    return list(
        db.scalars(
            select(Diagram)
            .where(
                Diagram.workspace_id == membership.workspace_id,
                Diagram.project_id == project_id,
                Diagram.status == ACTIVE_DIAGRAM_STATUS,
            )
            .order_by(Diagram.created_at.desc())
        )
    )


def list_workspace_diagrams(db: Session, *, membership: WorkspaceMember) -> list[Diagram]:
    return list(
        db.scalars(
            select(Diagram)
            .join(Project, Project.id == Diagram.project_id)
            .where(
                Diagram.workspace_id == membership.workspace_id,
                Diagram.status == ACTIVE_DIAGRAM_STATUS,
                Project.status == "active",
            )
            .order_by(Diagram.updated_at.desc())
        )
    )


def get_active_diagram(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, diagram_id: UUID
) -> Diagram:
    _ensure_project_access(db, membership=membership, project_id=project_id)
    diagram = db.scalar(
        select(Diagram).where(
            Diagram.id == diagram_id,
            Diagram.workspace_id == membership.workspace_id,
            Diagram.project_id == project_id,
            Diagram.status == ACTIVE_DIAGRAM_STATUS,
        )
    )
    if diagram is None:
        raise DiagramNotFoundError("Diagram not found")
    return diagram


def get_current_diagram_version(
    db: Session, *, diagram: Diagram
) -> DiagramVersion:
    version = db.scalar(
        select(DiagramVersion).where(
            DiagramVersion.diagram_id == diagram.id,
            DiagramVersion.workspace_id == diagram.workspace_id,
            DiagramVersion.project_id == diagram.project_id,
            DiagramVersion.version_number == diagram.current_version,
        )
    )
    if version is None:
        raise DiagramNotFoundError("Diagram version not found")
    return version


def get_diagram_detail(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, diagram_id: UUID
) -> tuple[Diagram, DiagramVersion]:
    diagram = get_active_diagram(
        db, membership=membership, project_id=project_id, diagram_id=diagram_id
    )
    return diagram, get_current_diagram_version(db, diagram=diagram)



def save_diagram_version(
    db: Session,
    *,
    membership: WorkspaceMember,
    project_id: UUID,
    diagram_id: UUID,
    drawio_xml: str,
    diagram_json: str | None,
) -> DiagramVersion:
    require_workspace_role(membership, allowed_roles=DIAGRAM_MUTATION_ROLES)
    diagram = get_active_diagram(
        db, membership=membership, project_id=project_id, diagram_id=diagram_id
    )
    next_version = diagram.current_version + 1
    version = DiagramVersion(
        workspace_id=membership.workspace_id,
        project_id=project_id,
        diagram_id=diagram_id,
        version_number=next_version,
        drawio_xml=_clean_required(drawio_xml, "Draw.io XML is required"),
        diagram_json=diagram_json,
        created_by_user_id=membership.user_id,
    )
    diagram.current_version = next_version
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def list_diagram_versions(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, diagram_id: UUID
) -> list[DiagramVersion]:
    get_active_diagram(db, membership=membership, project_id=project_id, diagram_id=diagram_id)
    return list(
        db.scalars(
            select(DiagramVersion)
            .where(
                DiagramVersion.workspace_id == membership.workspace_id,
                DiagramVersion.project_id == project_id,
                DiagramVersion.diagram_id == diagram_id,
            )
            .order_by(DiagramVersion.version_number.asc())
        )
    )

def update_diagram(
    db: Session,
    *,
    membership: WorkspaceMember,
    project_id: UUID,
    diagram_id: UUID,
    title: str | None,
) -> Diagram:
    require_workspace_role(membership, allowed_roles=DIAGRAM_MUTATION_ROLES)
    diagram = get_active_diagram(db, membership=membership, project_id=project_id, diagram_id=diagram_id)
    if title is not None:
        diagram.title = _clean_required(title, "Diagram title is required")
    db.commit()
    db.refresh(diagram)
    return diagram


def archive_diagram(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, diagram_id: UUID
) -> None:
    require_workspace_role(membership, allowed_roles=DIAGRAM_MUTATION_ROLES)
    diagram = get_active_diagram(db, membership=membership, project_id=project_id, diagram_id=diagram_id)
    diagram.status = ARCHIVED_DIAGRAM_STATUS
    db.commit()
