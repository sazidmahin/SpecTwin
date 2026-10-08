from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project, WorkspaceMember
from app.services.workspace_service import require_workspace_role

PROJECT_MUTATION_ROLES = {"owner", "admin", "member"}
ACTIVE_PROJECT_STATUS = "active"
ARCHIVED_PROJECT_STATUS = "archived"


class ProjectError(Exception):
    """Base class for expected project failures."""


class InvalidProjectError(ProjectError):
    pass


class ProjectNotFoundError(ProjectError):
    pass


def _clean_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = description.strip()
    return cleaned or None


def create_project(
    db: Session,
    *,
    membership: WorkspaceMember,
    name: str,
    description: str | None,
) -> Project:
    require_workspace_role(membership, allowed_roles=PROJECT_MUTATION_ROLES)
    cleaned_name = name.strip()
    if not cleaned_name:
        raise InvalidProjectError("Project name is required")

    project = Project(
        workspace_id=membership.workspace_id,
        name=cleaned_name,
        description=_clean_description(description),
        status=ACTIVE_PROJECT_STATUS,
        created_by_user_id=membership.user_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_active_projects(db: Session, *, workspace_id: UUID) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .where(
                Project.workspace_id == workspace_id,
                Project.status == ACTIVE_PROJECT_STATUS,
            )
            .order_by(Project.created_at.desc())
        )
    )


def get_active_project(db: Session, *, workspace_id: UUID, project_id: UUID) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
            Project.status == ACTIVE_PROJECT_STATUS,
        )
    )
    if project is None:
        raise ProjectNotFoundError("Project not found")
    return project


def update_project(
    db: Session,
    *,
    membership: WorkspaceMember,
    project_id: UUID,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> Project:
    require_workspace_role(membership, allowed_roles=PROJECT_MUTATION_ROLES)
    project = get_active_project(
        db, workspace_id=membership.workspace_id, project_id=project_id
    )

    if name is not None:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise InvalidProjectError("Project name is required")
        project.name = cleaned_name
    if description is not None:
        project.description = _clean_description(description)
    if status is not None:
        if status not in {ACTIVE_PROJECT_STATUS, ARCHIVED_PROJECT_STATUS}:
            raise InvalidProjectError("Invalid project status")
        project.status = status

    db.commit()
    db.refresh(project)
    return project


def archive_project(
    db: Session,
    *,
    membership: WorkspaceMember,
    project_id: UUID,
) -> Project:
    return update_project(
        db,
        membership=membership,
        project_id=project_id,
        status=ARCHIVED_PROJECT_STATUS,
    )