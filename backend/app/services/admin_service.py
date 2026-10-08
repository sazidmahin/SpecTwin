from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import (
    AdminAuditLog,
    Diagram,
    GenerationPipelineRun,
    LlmCall,
    PlatformSetting,
    PromptTemplate,
    Project,
    SrsDocument,
    User,
    Workspace,
)


def log_admin_action(
    db: Session,
    *,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AdminAuditLog:
    audit_log = AdminAuditLog(
        admin_user_id=admin_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log


def list_platform_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.asc())))


def list_platform_workspaces(db: Session) -> list[Workspace]:
    return list(db.scalars(select(Workspace).order_by(Workspace.created_at.asc())))


def list_platform_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.asc())))


def list_platform_pipeline_runs(db: Session) -> list[GenerationPipelineRun]:
    return list(db.scalars(select(GenerationPipelineRun).order_by(GenerationPipelineRun.created_at.desc())))


def platform_overview(db: Session) -> dict[str, int]:
    def count(model, *conditions) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)

    return {
        "users": count(User),
        "workspaces": count(Workspace),
        "projects": count(Project, Project.status == "active"),
        "pipeline_runs": count(GenerationPipelineRun),
        "completed_runs": count(GenerationPipelineRun, GenerationPipelineRun.status == "completed"),
        "srs_documents": count(SrsDocument, SrsDocument.status == "active"),
        "diagrams": count(Diagram, Diagram.status == "active"),
        "llm_calls": count(LlmCall),
    }


def list_platform_llm_calls(db: Session) -> list[LlmCall]:
    return list(db.scalars(select(LlmCall).order_by(LlmCall.created_at.asc())))


def list_prompt_templates(db: Session) -> list[PromptTemplate]:
    return list(db.scalars(select(PromptTemplate).order_by(PromptTemplate.name.asc(), PromptTemplate.version.asc())))


def list_admin_audit_logs(db: Session) -> list[AdminAuditLog]:
    return list(db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.asc())))


def list_platform_settings(db: Session) -> list[PlatformSetting]:
    return list(db.scalars(select(PlatformSetting).order_by(PlatformSetting.key.asc())))


def upsert_platform_setting(
    db: Session,
    *,
    key: str,
    value: Any,
    description: str | None,
) -> PlatformSetting:
    setting = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    if setting is None:
        setting = PlatformSetting(key=key, value=value, description=description)
        db.add(setting)
    else:
        setting.value = value
        setting.description = description
    db.commit()
    db.refresh(setting)
    return setting


def seed_super_admin_from_settings(db: Session) -> User | None:
    if not settings.super_admin_email or not settings.super_admin_password:
        return None

    return ensure_super_admin(
        db,
        email=settings.super_admin_email,
        password=settings.super_admin_password,
        full_name=settings.super_admin_full_name,
    )


def ensure_super_admin(db: Session, *, email: str, password: str, full_name: str) -> User | None:
    existing_super_admin = db.scalar(select(User).where(User.platform_role == "super_admin"))
    if existing_super_admin is not None:
        return None

    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip() or "Platform Super Admin",
            status="active",
            platform_role="super_admin",
            is_platform_admin=True,
        )
        db.add(user)
    else:
        user.password_hash = hash_password(password)
        user.full_name = user.full_name or full_name.strip() or "Platform Super Admin"
        user.status = "active"
        user.platform_role = "super_admin"
        user.is_platform_admin = True

    db.commit()
    db.refresh(user)
    return user
