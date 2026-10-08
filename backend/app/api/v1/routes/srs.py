from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_membership, get_db
from app.db.models import SrsDocument, WorkspaceMember
from app.schemas.srs import SrsDocumentRead, SrsDocumentUpdateRequest
from app.services.srs_service import (
    InvalidSrsRequestError,
    SrsDocumentNotFoundError,
    archive_srs_document,
    get_srs_document,
    list_srs_documents,
    list_workspace_srs_documents,
    update_srs_document,
)
from app.services.workspace_service import WorkspacePermissionError

router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects/{project_id}/srs",
    tags=["srs"],
)
workspace_router = APIRouter(prefix="/workspaces/{workspace_id}/srs-documents", tags=["srs"])


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, WorkspacePermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, SrsDocumentNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, InvalidSrsRequestError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    raise exc


@workspace_router.get("", response_model=list[SrsDocumentRead])
def get_workspace_srs_documents(
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[SrsDocument]:
    return list_workspace_srs_documents(db, membership=membership)


@router.get("", response_model=list[SrsDocumentRead])
def get_srs_documents(
    project_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[SrsDocument]:
    try:
        return list_srs_documents(db, membership=membership, project_id=project_id)
    except SrsDocumentNotFoundError as exc:
        _raise_http(exc)
        raise


@router.get("/{srs_document_id}/export", response_class=Response)
def export_srs_document(
    project_id: UUID,
    srs_document_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        document = get_srs_document(
            db, membership=membership, project_id=project_id, srs_document_id=srs_document_id
        )
    except SrsDocumentNotFoundError as exc:
        _raise_http(exc)
        raise

    filename = f"{document.title.strip().replace(' ', '-') or 'srs-document'}.md"
    return Response(
        content=document.content_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{srs_document_id}", response_model=SrsDocumentRead)
def get_srs_document_detail(
    project_id: UUID,
    srs_document_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> SrsDocument:
    try:
        return get_srs_document(db, membership=membership, project_id=project_id, srs_document_id=srs_document_id)
    except SrsDocumentNotFoundError as exc:
        _raise_http(exc)
        raise


@router.patch("/{srs_document_id}", response_model=SrsDocumentRead)
def patch_srs_document(
    project_id: UUID,
    srs_document_id: UUID,
    payload: SrsDocumentUpdateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> SrsDocument:
    try:
        return update_srs_document(
            db,
            membership=membership,
            project_id=project_id,
            srs_document_id=srs_document_id,
            title=payload.title,
            content_markdown=payload.content_markdown,
        )
    except (WorkspacePermissionError, SrsDocumentNotFoundError, InvalidSrsRequestError) as exc:
        _raise_http(exc)
        raise


@router.delete("/{srs_document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_srs_document(
    project_id: UUID,
    srs_document_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        archive_srs_document(db, membership=membership, project_id=project_id, srs_document_id=srs_document_id)
    except (WorkspacePermissionError, SrsDocumentNotFoundError) as exc:
        _raise_http(exc)
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
