from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.db.models import AdminAuditLog, User
from app.schemas.admin import (
    AdminAuditLogRead,
    AdminOverviewRead,
    AdminPipelineRunRead,
    AdminLlmCallRead,
    AdminProjectRead,
    AdminPromptTemplateRead,
    AdminUserRead,
    AdminWorkspaceRead,
    PlatformSettingRead,
    PlatformSettingUpsertRequest,
)
from app.services.admin_service import (
    list_admin_audit_logs,
    list_platform_pipeline_runs,
    list_platform_llm_calls,
    list_platform_projects,
    list_platform_settings,
    platform_overview,
    list_platform_users,
    list_platform_workspaces,
    list_prompt_templates,
    log_admin_action,
    upsert_platform_setting,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _request_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _audit(
    db: Session,
    request: Request,
    *,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: UUID | None = None,
    result_count: int | None = None,
) -> None:
    metadata = {"result_count": result_count} if result_count is not None else None
    log_admin_action(
        db,
        admin_user=admin_user,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
        ip_address=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


def _audit_log_response(audit_log: AdminAuditLog) -> AdminAuditLogRead:
    return AdminAuditLogRead(
        id=audit_log.id,
        admin_user_id=audit_log.admin_user_id,
        action=audit_log.action,
        target_type=audit_log.target_type,
        target_id=audit_log.target_id,
        metadata=audit_log.metadata_json,
        ip_address=audit_log.ip_address,
        user_agent=audit_log.user_agent,
        created_at=audit_log.created_at,
    )


@router.get("/users", response_model=list[AdminUserRead])
def admin_list_users(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    users = list_platform_users(db)
    _audit(db, request, admin_user=admin_user, action="admin.users.list", target_type="user", result_count=len(users))
    return users


@router.get("/workspaces", response_model=list[AdminWorkspaceRead])
def admin_list_workspaces(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    workspaces = list_platform_workspaces(db)
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.workspaces.list",
        target_type="workspace",
        result_count=len(workspaces),
    )
    return workspaces


@router.get("/overview", response_model=AdminOverviewRead)
def admin_overview(
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    del admin_user
    return platform_overview(db)


@router.get("/projects", response_model=list[AdminProjectRead])
def admin_list_projects(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    projects = list_platform_projects(db)
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.projects.list",
        target_type="project",
        result_count=len(projects),
    )
    return projects


@router.get("/pipeline-runs", response_model=list[AdminPipelineRunRead])
def admin_list_pipeline_runs(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    runs = list_platform_pipeline_runs(db)
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.pipeline_runs.list",
        target_type="pipeline_run",
        result_count=len(runs),
    )
    return runs


@router.get("/llm-calls", response_model=list[AdminLlmCallRead])
def admin_list_llm_calls(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    llm_calls = list_platform_llm_calls(db)
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.llm_calls.list",
        target_type="llm_call",
        result_count=len(llm_calls),
    )
    return llm_calls


@router.get("/prompt-templates", response_model=list[AdminPromptTemplateRead])
def admin_list_prompt_templates(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    templates = list_prompt_templates(db)
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.prompt_templates.list",
        target_type="prompt_template",
        result_count=len(templates),
    )
    return templates


@router.get("/audit-logs", response_model=list[AdminAuditLogRead])
def admin_list_audit_logs(
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> list[AdminAuditLogRead]:
    del admin_user
    return [_audit_log_response(audit_log) for audit_log in list_admin_audit_logs(db)]


@router.get("/platform-settings", response_model=list[PlatformSettingRead])
def admin_list_platform_settings(
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    settings = list_platform_settings(db)
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.platform_settings.list",
        target_type="platform_setting",
        result_count=len(settings),
    )
    return settings


@router.put(
    "/platform-settings/{key}",
    response_model=PlatformSettingRead,
    status_code=status.HTTP_200_OK,
)
def admin_upsert_platform_setting(
    key: str,
    payload: PlatformSettingUpsertRequest,
    request: Request,
    admin_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    setting = upsert_platform_setting(
        db,
        key=key,
        value=payload.value,
        description=payload.description,
    )
    _audit(
        db,
        request,
        admin_user=admin_user,
        action="admin.platform_settings.upsert",
        target_type="platform_setting",
        target_id=setting.id,
    )
    return setting
