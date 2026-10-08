from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401
from app.db.base import Base
from app.main import app


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


def invitation_token(invite_response) -> str:
    return invite_response.json()["invite_url"].rsplit("/", 1)[-1]


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


def personal_workspace_id(client: TestClient, token: str) -> str:
    response = client.get("/api/v1/workspaces", headers=auth_header(token))
    assert response.status_code == 200
    return response.json()[0]["workspace"]["id"]


def create_project(client: TestClient, token: str, workspace_id: str, name: str) -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=auth_header(token),
        json={"name": name, "description": "Initial requirements"},
    )
    assert response.status_code == 201
    return response.json()


def test_project_crud_flow_is_scoped_to_workspace(client: TestClient) -> None:
    owner_token = register(client, "owner@example.com", "Owner User")
    other_token = register(client, "other@example.com", "Other User")
    workspace_id = personal_workspace_id(client, owner_token)
    other_workspace_id = personal_workspace_id(client, other_token)

    project = create_project(client, owner_token, workspace_id, "Claims Portal")

    list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/projects", headers=auth_header(owner_token)
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [project["id"]]

    detail_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/projects/{project['id']}",
        headers=auth_header(owner_token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["workspace_id"] == workspace_id

    wrong_workspace_response = client.get(
        f"/api/v1/workspaces/{other_workspace_id}/projects/{project['id']}",
        headers=auth_header(other_token),
    )
    assert wrong_workspace_response.status_code == 404

    update_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/projects/{project['id']}",
        headers=auth_header(owner_token),
        json={"name": "Claims Portal MVP", "description": "Updated requirements"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Claims Portal MVP"
    assert update_response.json()["description"] == "Updated requirements"

    archive_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects/{project['id']}/archive",
        headers=auth_header(owner_token),
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    empty_list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/projects", headers=auth_header(owner_token)
    )
    assert empty_list_response.status_code == 200
    assert empty_list_response.json() == []

    archived_detail_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/projects/{project['id']}",
        headers=auth_header(owner_token),
    )
    assert archived_detail_response.status_code == 404


def test_viewer_can_list_projects_but_cannot_mutate(client: TestClient) -> None:
    owner_token = register(client, "owner@example.com", "Owner User")
    viewer_token = register(client, "viewer@example.com", "Viewer User")
    create_workspace_response = client.post(
        "/api/v1/workspaces",
        headers=auth_header(owner_token),
        json={"name": "Research Team", "slug": "research-team", "type": "organization"},
    )
    assert create_workspace_response.status_code == 201
    workspace_id = create_workspace_response.json()["workspace"]["id"]
    project = create_project(client, owner_token, workspace_id, "Research Hub")

    invite_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members/invite",
        headers=auth_header(owner_token),
        json={"email": "viewer@example.com", "role": "viewer"},
    )
    assert invite_response.status_code == 201
    accept_response = client.post(
        f"/api/v1/invitations/{invitation_token(invite_response)}/accept",
        headers=auth_header(viewer_token),
    )
    assert accept_response.status_code == 200

    list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/projects", headers=auth_header(viewer_token)
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    create_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=auth_header(viewer_token),
        json={"name": "Viewer Project", "description": None},
    )
    assert create_response.status_code == 403

    update_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/projects/{project['id']}",
        headers=auth_header(viewer_token),
        json={"name": "Viewer Rename"},
    )
    assert update_response.status_code == 403

    archive_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects/{project['id']}/archive",
        headers=auth_header(viewer_token),
    )
    assert archive_response.status_code == 403
