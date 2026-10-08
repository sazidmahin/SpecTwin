from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_membership, get_db
from app.db.models import Diagram, DiagramVersion, WorkspaceMember
from app.schemas.diagram import (
    DiagramCreateRequest,
    DiagramDetailRead,
    DiagramRead,
    DiagramUpdateRequest,
    DiagramVersionCreateRequest,
    DiagramVersionRead,
)
from app.services.diagram_service import (
    DiagramNotFoundError,
    InvalidDiagramError,
    archive_diagram,
    create_manual_diagram,
    get_diagram_detail,
    list_active_diagrams,
    list_diagram_versions,
    list_workspace_diagrams,
    save_diagram_version,
    update_diagram,
)
from app.services.workspace_service import WorkspacePermissionError

router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects/{project_id}/diagrams",
    tags=["diagrams"],
)
workspace_router = APIRouter(prefix="/workspaces/{workspace_id}/diagrams", tags=["diagrams"])


@workspace_router.get("", response_model=list[DiagramRead])
def list_workspace_diagrams_route(
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[Diagram]:
    return list_workspace_diagrams(db, membership=membership)


def _detail_response(diagram: Diagram, current: DiagramVersion) -> DiagramDetailRead:
    return DiagramDetailRead.model_validate({**diagram.__dict__, "current": current})


def _load_detail_response(
    db: Session, *, membership: WorkspaceMember, project_id: UUID, diagram_id: UUID
) -> DiagramDetailRead:
    diagram, current = get_diagram_detail(
        db, membership=membership, project_id=project_id, diagram_id=diagram_id
    )
    return _detail_response(diagram, current)


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, WorkspacePermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, DiagramNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, InvalidDiagramError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    raise exc


@router.post("", response_model=DiagramDetailRead, status_code=status.HTTP_201_CREATED)
def create_diagram(
    project_id: UUID,
    payload: DiagramCreateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> DiagramDetailRead:
    try:
        diagram = create_manual_diagram(
            db,
            membership=membership,
            project_id=project_id,
            title=payload.title,
            diagram_type=payload.diagram_type,
            drawio_xml=payload.drawio_xml,
            diagram_json=payload.diagram_json,
        )
        return _load_detail_response(db, membership=membership, project_id=project_id, diagram_id=diagram.id)
    except (WorkspacePermissionError, DiagramNotFoundError, InvalidDiagramError) as exc:
        _raise_http(exc)
        raise


@router.get("", response_model=list[DiagramRead])
def list_diagrams(
    project_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[Diagram]:
    try:
        return list_active_diagrams(db, membership=membership, project_id=project_id)
    except DiagramNotFoundError as exc:
        _raise_http(exc)
        raise


@router.get("/{diagram_id}/export", response_class=Response)
def export_diagram(
    project_id: UUID,
    diagram_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        diagram, current = get_diagram_detail(
            db, membership=membership, project_id=project_id, diagram_id=diagram_id
        )
    except DiagramNotFoundError as exc:
        _raise_http(exc)
        raise

    filename = f"{diagram.title.strip().replace(' ', '-') or 'diagram'}.drawio"
    return Response(
        content=current.drawio_xml,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{diagram_id}", response_model=DiagramDetailRead)
def get_diagram(
    project_id: UUID,
    diagram_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> DiagramDetailRead:
    try:
        return _load_detail_response(db, membership=membership, project_id=project_id, diagram_id=diagram_id)
    except DiagramNotFoundError as exc:
        _raise_http(exc)
        raise


@router.patch("/{diagram_id}", response_model=DiagramRead)
def patch_diagram(
    project_id: UUID,
    diagram_id: UUID,
    payload: DiagramUpdateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Diagram:
    try:
        return update_diagram(
            db, membership=membership, project_id=project_id, diagram_id=diagram_id, title=payload.title
        )
    except (WorkspacePermissionError, DiagramNotFoundError, InvalidDiagramError) as exc:
        _raise_http(exc)
        raise


@router.delete("/{diagram_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diagram(
    project_id: UUID,
    diagram_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        archive_diagram(db, membership=membership, project_id=project_id, diagram_id=diagram_id)
    except (WorkspacePermissionError, DiagramNotFoundError) as exc:
        _raise_http(exc)
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{diagram_id}/versions",
    response_model=DiagramVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_diagram_version(
    project_id: UUID,
    diagram_id: UUID,
    payload: DiagramVersionCreateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> DiagramVersion:
    try:
        return save_diagram_version(
            db,
            membership=membership,
            project_id=project_id,
            diagram_id=diagram_id,
            drawio_xml=payload.drawio_xml,
            diagram_json=payload.diagram_json,
        )
    except (WorkspacePermissionError, DiagramNotFoundError, InvalidDiagramError) as exc:
        _raise_http(exc)
        raise


@router.get("/{diagram_id}/versions", response_model=list[DiagramVersionRead])
def get_versions(
    project_id: UUID,
    diagram_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[DiagramVersion]:
    try:
        return list_diagram_versions(
            db, membership=membership, project_id=project_id, diagram_id=diagram_id
        )
    except DiagramNotFoundError as exc:
        _raise_http(exc)
        raise
