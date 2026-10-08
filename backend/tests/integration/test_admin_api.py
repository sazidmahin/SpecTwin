from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import hash_password, verify_password
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import AdminAuditLog, PlatformSetting, User
from app.main import app
from app.services.admin_service import ensure_super_admin


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, email: str, full_name: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "full_name": full_name},
    )
    assert response.status_code == 202
    code = response.json()["verification_code"]
    assert code

    verify_response = client.post(
        "/api/v1/auth/verify-email", json={"email": email, "code": code}
    )
    assert verify_response.status_code == 200
    return verify_response.json()["access_token"]


def promote_to_super_admin(db_session: Session, email: str) -> User:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.platform_role = "super_admin"
    user.is_platform_admin = True
    db_session.commit()
    db_session.refresh(user)
    return user


def personal_workspace_id(client: TestClient, token: str) -> str:
    response = client.get("/api/v1/workspaces", headers=auth_header(token))
    assert response.status_code == 200
    return response.json()[0]["workspace"]["id"]


def test_admin_routes_require_super_admin(client: TestClient, db_session: Session) -> None:
    token = register(client, "user@example.com", "Normal User")

    denied_response = client.get("/api/v1/admin/users", headers=auth_header(token))
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"] == "Platform super admin access required"

    user = db_session.scalar(select(User).where(User.email == "user@example.com"))
    assert user is not None
    assert user.platform_role == "user"
    assert user.is_platform_admin is False


def test_super_admin_can_view_platform_resources_and_audit_reads(
    client: TestClient, db_session: Session
) -> None:
    admin_token = register(client, "admin@example.com", "Admin User")
    admin_user = promote_to_super_admin(db_session, "admin@example.com")
    member_token = register(client, "member@example.com", "Member User")
    workspace_id = personal_workspace_id(client, member_token)

    project_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=auth_header(member_token),
        json={"name": "Admin Visible Project", "description": "Listed by admin"},
    )
    assert project_response.status_code == 201

    endpoints = {
        "users": "/api/v1/admin/users",
        "workspaces": "/api/v1/admin/workspaces",
        "overview": "/api/v1/admin/overview",
        "projects": "/api/v1/admin/projects",
        "pipeline_runs": "/api/v1/admin/pipeline-runs",
        "llm_calls": "/api/v1/admin/llm-calls",
    }
    responses = {
        name: client.get(path, headers=auth_header(admin_token)) for name, path in endpoints.items()
    }

    assert all(response.status_code == 200 for response in responses.values())
    assert {user["email"] for user in responses["users"].json()} == {
        "admin@example.com",
        "member@example.com",
    }
    assert any(user["platform_role"] == "super_admin" for user in responses["users"].json())
    assert any(workspace["id"] == workspace_id for workspace in responses["workspaces"].json())
    assert any(project["name"] == "Admin Visible Project" for project in responses["projects"].json())
    assert responses["overview"].json()["users"] == 2
    assert responses["overview"].json()["projects"] == 1
    assert responses["pipeline_runs"].json() == []
    assert responses["llm_calls"].json() == []

    audit_logs = list(db_session.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.asc())))
    assert {log.action for log in audit_logs}.issuperset(
        {
            "admin.users.list",
            "admin.workspaces.list",
            "admin.projects.list",
            "admin.pipeline_runs.list",
            "admin.llm_calls.list",
        }
    )
    assert all(log.admin_user_id == admin_user.id for log in audit_logs)


def test_super_admin_can_manage_platform_settings_and_read_audit_log(
    client: TestClient, db_session: Session
) -> None:
    admin_token = register(client, "settings-admin@example.com", "Settings Admin")
    promote_to_super_admin(db_session, "settings-admin@example.com")

    upsert_response = client.put(
        "/api/v1/admin/platform-settings/maintenance_mode",
        headers=auth_header(admin_token),
        json={"value": False, "description": "Controls platform-wide maintenance banner"},
    )
    assert upsert_response.status_code == 200
    assert upsert_response.json()["key"] == "maintenance_mode"
    assert upsert_response.json()["value"] is False

    settings_response = client.get(
        "/api/v1/admin/platform-settings", headers=auth_header(admin_token)
    )
    assert settings_response.status_code == 200
    assert settings_response.json()[0]["key"] == "maintenance_mode"

    audit_response = client.get("/api/v1/admin/audit-logs", headers=auth_header(admin_token))
    assert audit_response.status_code == 200
    assert {entry["action"] for entry in audit_response.json()} == {
        "admin.platform_settings.upsert",
        "admin.platform_settings.list",
    }

    setting = db_session.scalar(select(PlatformSetting).where(PlatformSetting.key == "maintenance_mode"))
    assert setting is not None
    assert setting.value is False


def test_ensure_super_admin_promotes_existing_user_and_blocks_second_admin(
    db_session: Session,
) -> None:
    existing_user = User(
        email="seedadmin@example.com",
        password_hash=hash_password("old-password"),
        full_name="Seed Admin",
        status="active",
    )
    db_session.add(existing_user)
    db_session.commit()

    promoted = ensure_super_admin(
        db_session,
        email="SeedAdmin@example.com",
        password="first-password",
        full_name="Seed Admin",
    )
    assert promoted is not None
    assert promoted.id == existing_user.id
    assert promoted.email == "seedadmin@example.com"
    assert promoted.platform_role == "super_admin"
    assert promoted.is_platform_admin is True
    assert verify_password("first-password", promoted.password_hash)

    second = ensure_super_admin(
        db_session,
        email="second@example.com",
        password="second-password",
        full_name="Second Admin",
    )
    assert second is None
    assert db_session.scalar(select(User).where(User.email == "second@example.com")) is None

