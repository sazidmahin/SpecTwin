from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_membership, get_db
from app.db.models import Project, WorkspaceMember
from app.schemas.project import ProjectCreateRequest, ProjectRead, ProjectUpdateRequest
from app.services.project_service import (
    InvalidProjectError,
    ProjectNotFoundError,
    archive_project,
    create_project,
    get_active_project,
    list_active_projects,
    update_project,
)
from app.services.workspace_service import WorkspacePermissionError

router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects",
    tags=["projects"],
)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_workspace_project(
    payload: ProjectCreateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Project:
    try:
        return create_project(
            db,
            membership=membership,
            name=payload.name,
            description=payload.description,
        )
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidProjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("", response_model=list[ProjectRead])
def list_workspace_projects(
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[Project]:
    return list_active_projects(db, workspace_id=membership.workspace_id)


@router.get("/{project_id}", response_model=ProjectRead)
def get_workspace_project(
    project_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Project:
    try:
        return get_active_project(
            db, workspace_id=membership.workspace_id, project_id=project_id
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{project_id}", response_model=ProjectRead)
def update_workspace_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Project:
    try:
        return update_project(
            db,
            membership=membership,
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidProjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post("/{project_id}/archive", response_model=ProjectRead)
def archive_workspace_project(
    project_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Project:
    try:
        return archive_project(db, membership=membership, project_id=project_id)
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
