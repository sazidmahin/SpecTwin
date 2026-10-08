from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_membership, get_db
from app.db.models import WorkspaceMember
from app.schemas.generation_pipeline import (
    PipelineClassMutationRequest,
    PipelineRunCreateRequest,
    PipelineRunRead,
    PipelineRunSummaryRead,
    PipelineRunUpdateRequest,
    PipelineStageApproveRequest,
    PipelineStageRevisionCreateRequest,
    PipelineStageRevisionRead,
)
from app.services.ai_settings_service import AiSettingsError
from app.services.generation_pipeline_service import (
    GenerationPipelineError,
    GenerationPipelineNotFoundError,
    GenerationPipelineStateError,
    add_class,
    add_relationship,
    approve_stage,
    create_pipeline_run,
    delete_pipeline_run,
    delete_class,
    delete_relationship,
    generate_next_stage,
    get_pipeline_run,
    list_pipeline_runs,
    list_workspace_pipeline_runs,
    mutate_class_model,
    patch_class,
    patch_relationship,
    rename_pipeline_run,
    reopen_stage,
    save_stage_revision,
)
from app.services.llm_service import LlmConfigurationError, LlmExecutionError
from app.services.project_service import ProjectNotFoundError
from app.services.workspace_service import WorkspacePermissionError

router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects/{project_id}/generation-pipelines",
    tags=["generation-pipelines"],
)
workspace_router = APIRouter(prefix="/workspaces/{workspace_id}/generation-pipelines", tags=["generation-pipelines"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (GenerationPipelineNotFoundError, ProjectNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, WorkspacePermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, GenerationPipelineStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


EXPECTED_ERRORS = (
    GenerationPipelineError,
    AiSettingsError,
    LlmConfigurationError,
    LlmExecutionError,
    ProjectNotFoundError,
    WorkspacePermissionError,
)


@router.post("", response_model=PipelineRunRead, status_code=status.HTTP_201_CREATED)
def create_run(
    project_id: UUID,
    payload: PipelineRunCreateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return create_pipeline_run(db, membership=membership, project_id=project_id, **payload.model_dump())
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@workspace_router.get("", response_model=list[PipelineRunSummaryRead])
def get_workspace_runs(
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_workspace_pipeline_runs(db, membership=membership)


@router.get("", response_model=list[PipelineRunSummaryRead])
def get_runs(
    project_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> list[dict]:
    try:
        return list_pipeline_runs(db, membership=membership, project_id=project_id)
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get("/{run_id}", response_model=PipelineRunRead)
def get_run(
    project_id: UUID,
    run_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return get_pipeline_run(db, membership=membership, project_id=project_id, run_id=run_id)
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.patch("/{run_id}", response_model=PipelineRunRead)
def patch_run(
    project_id: UUID,
    run_id: UUID,
    payload: PipelineRunUpdateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return rename_pipeline_run(db, membership=membership, project_id=project_id, run_id=run_id, title=payload.title)
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    project_id: UUID,
    run_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_pipeline_run(db, membership=membership, project_id=project_id, run_id=run_id)
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{run_id}/next", response_model=PipelineRunRead)
def next_stage(
    project_id: UUID,
    run_id: UUID,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return generate_next_stage(db, membership=membership, project_id=project_id, run_id=run_id)
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/{run_id}/stages/{stage_name}/revisions", response_model=PipelineStageRevisionRead)
def save_revision(
    project_id: UUID,
    run_id: UUID,
    stage_name: str,
    payload: PipelineStageRevisionCreateRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return save_stage_revision(
            db,
            membership=membership,
            project_id=project_id,
            run_id=run_id,
            stage_name=stage_name,
            **payload.model_dump(),
        )
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/{run_id}/stages/{stage_name}/approve", response_model=PipelineRunRead)
def approve(
    project_id: UUID,
    run_id: UUID,
    stage_name: str,
    payload: PipelineStageApproveRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return approve_stage(
            db,
            membership=membership,
            project_id=project_id,
            run_id=run_id,
            stage_name=stage_name,
            **payload.model_dump(),
        )
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/{run_id}/stages/{stage_name}/reopen", response_model=PipelineStageRevisionRead)
def reopen(
    project_id: UUID,
    run_id: UUID,
    stage_name: str,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return reopen_stage(
            db,
            membership=membership,
            project_id=project_id,
            run_id=run_id,
            stage_name=stage_name,
        )
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


def _mutate(
    db: Session,
    membership: WorkspaceMember,
    project_id: UUID,
    run_id: UUID,
    payload: PipelineClassMutationRequest,
    updater,
) -> dict:
    return mutate_class_model(
        db,
        membership=membership,
        project_id=project_id,
        run_id=run_id,
        expected_version=payload.expected_version,
        updater=updater,
    )


@router.post("/{run_id}/class-model/classes", response_model=PipelineStageRevisionRead)
def create_class_definition(
    project_id: UUID,
    run_id: UUID,
    payload: PipelineClassMutationRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return _mutate(db, membership, project_id, run_id, payload, lambda data: add_class(data, payload.data))
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.patch("/{run_id}/class-model/classes/{class_id}", response_model=PipelineStageRevisionRead)
def update_class_definition(
    project_id: UUID,
    run_id: UUID,
    class_id: str,
    payload: PipelineClassMutationRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return _mutate(db, membership, project_id, run_id, payload, lambda data: patch_class(data, class_id, payload.data))
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.delete("/{run_id}/class-model/classes/{class_id}", response_model=PipelineStageRevisionRead)
def remove_class_definition(
    project_id: UUID,
    run_id: UUID,
    class_id: str,
    expected_version: int | None = None,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        payload = PipelineClassMutationRequest(data={}, expected_version=expected_version)
        return _mutate(db, membership, project_id, run_id, payload, lambda data: delete_class(data, class_id))
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/{run_id}/class-model/relationships", response_model=PipelineStageRevisionRead)
def create_relationship_definition(
    project_id: UUID,
    run_id: UUID,
    payload: PipelineClassMutationRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return _mutate(db, membership, project_id, run_id, payload, lambda data: add_relationship(data, payload.data))
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.patch("/{run_id}/class-model/relationships/{relationship_id}", response_model=PipelineStageRevisionRead)
def update_relationship_definition(
    project_id: UUID,
    run_id: UUID,
    relationship_id: str,
    payload: PipelineClassMutationRequest,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return _mutate(
            db,
            membership,
            project_id,
            run_id,
            payload,
            lambda data: patch_relationship(data, relationship_id, payload.data),
        )
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc


@router.delete("/{run_id}/class-model/relationships/{relationship_id}", response_model=PipelineStageRevisionRead)
def remove_relationship_definition(
    project_id: UUID,
    run_id: UUID,
    relationship_id: str,
    expected_version: int | None = None,
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict:
    try:
        payload = PipelineClassMutationRequest(data={}, expected_version=expected_version)
        return _mutate(
            db,
            membership,
            project_id,
            run_id,
            payload,
            lambda data: delete_relationship(data, relationship_id),
        )
    except EXPECTED_ERRORS as exc:
        raise _http_error(exc) from exc
