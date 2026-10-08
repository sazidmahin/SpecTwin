from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import Workspace, WorkspaceMember
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


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def invitation_token(invite_response) -> str:
    return invite_response.json()["invite_url"].rsplit("/", 1)[-1]


def create_organization(client: TestClient, token: str, slug: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        headers=auth_header(token),
        json={"name": "Product Team", "slug": slug, "type": "organization"},
    )
    assert response.status_code == 201
    return response.json()["workspace"]["id"]


def invite(client: TestClient, token: str, workspace_id: str, email: str, role: str = "member"):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/members/invite",
        headers=auth_header(token),
        json={"email": email, "role": role},
    )


def accept(client: TestClient, token: str, invite_token: str):
    return client.post(f"/api/v1/invitations/{invite_token}/accept", headers=auth_header(token))


def test_list_workspaces_returns_only_current_users_active_memberships(
    client: TestClient, db_session: Session
) -> None:
    ada_token = register(client, "ada@example.com", "Ada Lovelace")
    bob_token = register(client, "bob@example.com", "Bob Stone")

    response = client.get("/api/v1/workspaces", headers=auth_header(ada_token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["workspace"]["type"] == "personal"
    assert body[0]["role"] == "owner"

    bob_workspace = db_session.scalar(
        select(Workspace).where(Workspace.slug.like("bob-stone-%"))
    )
    assert bob_workspace is not None

    forbidden_response = client.get(
        f"/api/v1/workspaces/{bob_workspace.id}", headers=auth_header(ada_token)
    )
    assert forbidden_response.status_code == 404

    bob_response = client.get("/api/v1/workspaces", headers=auth_header(bob_token))
    assert bob_response.status_code == 200
    assert len(bob_response.json()) == 1


def test_create_organization_workspace_adds_owner_membership(
    client: TestClient, db_session: Session
) -> None:
    token = register(client, "owner@example.com", "Owner User")

    response = client.post(
        "/api/v1/workspaces",
        headers=auth_header(token),
        json={"name": "Design Team", "slug": "design-team", "type": "organization"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workspace"]["name"] == "Design Team"
    assert body["workspace"]["slug"] == "design-team"
    assert body["workspace"]["type"] == "organization"
    assert body["role"] == "owner"

    workspace = db_session.scalar(select(Workspace).where(Workspace.slug == "design-team"))
    assert workspace is not None
    membership = db_session.scalar(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id)
    )
    assert membership is not None
    assert membership.role == "owner"


def test_workspace_detail_requires_active_membership(client: TestClient) -> None:
    owner_token = register(client, "owner@example.com", "Owner User")
    other_token = register(client, "other@example.com", "Other User")
    create_response = client.post(
        "/api/v1/workspaces",
        headers=auth_header(owner_token),
        json={"name": "API Team", "slug": "api-team", "type": "organization"},
    )
    workspace_id = create_response.json()["workspace"]["id"]

    owner_response = client.get(
        f"/api/v1/workspaces/{workspace_id}", headers=auth_header(owner_token)
    )
    other_response = client.get(
        f"/api/v1/workspaces/{workspace_id}", headers=auth_header(other_token)
    )

    assert owner_response.status_code == 200
    assert other_response.status_code == 404


def test_owner_can_invite_registered_user_and_member_cannot_manage_members(
    client: TestClient,
) -> None:
    owner_token = register(client, "owner@example.com", "Owner User")
    member_token = register(client, "member@example.com", "Member User")
    create_response = client.post(
        "/api/v1/workspaces",
        headers=auth_header(owner_token),
        json={"name": "Product Team", "slug": "product-team", "type": "organization"},
    )
    workspace_id = create_response.json()["workspace"]["id"]

    invite_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/members/invite",
        headers=auth_header(owner_token),
        json={"email": "member@example.com", "role": "member"},
    )

    assert invite_response.status_code == 201
    assert invite_response.json()["role"] == "member"
    assert invite_response.json()["status"] == "pending"

    # Inviting does not add the member until they accept the emailed link.
    members_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/members", headers=auth_header(owner_token)
    )
    assert len(members_response.json()) == 1

    accept_response = accept(client, member_token, invitation_token(invite_response))
    assert accept_response.status_code == 200
    assert accept_response.json()["workspace"]["id"] == workspace_id
    assert accept_response.json()["role"] == "member"

    members_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/members", headers=auth_header(owner_token)
    )
    assert members_response.status_code == 200
    assert len(members_response.json()) == 2

    forbidden_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/members", headers=auth_header(member_token)
    )
    assert forbidden_response.status_code == 403



def test_organization_admin_can_change_role_and_remove_member(client: TestClient) -> None:
    owner_token = register(client, "org-owner@example.com", "Org Owner")
    member_token = register(client, "org-member@example.com", "Org Member")
    workspace = client.post(
        "/api/v1/workspaces",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-roles", "type": "organization"},
    ).json()["workspace"]
    invited = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members/invite",
        headers=auth_header(owner_token),
        json={"email": "org-member@example.com", "role": "member"},
    )
    assert invited.status_code == 201
    joined = accept(client, member_token, invitation_token(invited))
    assert joined.status_code == 200

    members = client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=auth_header(owner_token)).json()
    member_id = next(item["id"] for item in members if item["user"]["email"] == "org-member@example.com")
    assert {item["user"]["email"] for item in members} == {"org-owner@example.com", "org-member@example.com"}

    promoted = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{member_id}",
        headers=auth_header(owner_token),
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    owner_id = next(item["id"] for item in members if item["role"] == "owner")
    assert client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}", headers=auth_header(owner_token)
    ).status_code == 422

    removed = client.delete(f"/api/v1/workspaces/{workspace['id']}/members/{member_id}", headers=auth_header(owner_token))
    assert removed.status_code == 204
    members = client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=auth_header(owner_token)).json()
    assert [item["user"]["email"] for item in members] == ["org-owner@example.com"]

    reinvited = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members/invite",
        headers=auth_header(owner_token),
        json={"email": "org-member@example.com", "role": "viewer"},
    )
    assert reinvited.status_code == 201
    assert reinvited.json()["role"] == "viewer"
    rejoined = accept(client, member_token, invitation_token(reinvited))
    assert rejoined.status_code == 200
    assert rejoined.json()["role"] == "viewer"


def test_invited_email_without_account_can_register_and_join(client: TestClient) -> None:
    owner_token = register(client, "lead@example.com", "Team Lead")
    workspace_id = create_organization(client, owner_token, "new-hires")

    invited = invite(client, owner_token, workspace_id, "Newcomer@Example.com", "viewer")
    assert invited.status_code == 201
    assert invited.json()["email"] == "newcomer@example.com"
    token = invitation_token(invited)

    preview = client.get(f"/api/v1/invitations/{token}")
    assert preview.status_code == 200
    assert preview.json() == {
        **preview.json(),
        "workspace_name": "Product Team",
        "inviter_name": "Team Lead",
        "email": "newcomer@example.com",
        "role": "viewer",
        "status": "pending",
        "account_exists": False,
    }

    newcomer_token = register(client, "newcomer@example.com", "Newcomer")
    assert client.get(f"/api/v1/invitations/{token}").json()["account_exists"] is True

    joined = accept(client, newcomer_token, token)
    assert joined.status_code == 200
    assert joined.json()["role"] == "viewer"

    workspaces = client.get("/api/v1/workspaces", headers=auth_header(newcomer_token)).json()
    assert workspace_id in {item["workspace"]["id"] for item in workspaces}

    # A link works once.
    assert accept(client, newcomer_token, token).status_code == 410
    assert client.get(f"/api/v1/invitations/{token}").json()["status"] == "accepted"


def test_invitation_must_be_accepted_by_the_invited_email(client: TestClient) -> None:
    owner_token = register(client, "boss@example.com", "Boss")
    other_token = register(client, "other@example.com", "Other")
    workspace_id = create_organization(client, owner_token, "private-team")

    invited = invite(client, owner_token, workspace_id, "someone@example.com")
    response = accept(client, other_token, invitation_token(invited))

    assert response.status_code == 403
    assert "someone@example.com" in response.json()["detail"]
    assert client.post("/api/v1/invitations/not-a-real-token/accept", headers=auth_header(other_token)).status_code == 404
    assert client.get("/api/v1/invitations/not-a-real-token").status_code == 404


def test_pending_invitations_can_be_listed_refreshed_and_revoked(client: TestClient) -> None:
    owner_token = register(client, "admin@example.com", "Admin")
    invitee_token = register(client, "invitee@example.com", "Invitee")
    workspace_id = create_organization(client, owner_token, "revoke-team")

    first = invite(client, owner_token, workspace_id, "invitee@example.com", "member")
    second = invite(client, owner_token, workspace_id, "invitee@example.com", "admin")
    assert first.json()["id"] == second.json()["id"]

    pending = client.get(f"/api/v1/workspaces/{workspace_id}/invitations", headers=auth_header(owner_token))
    assert pending.status_code == 200
    assert [(item["email"], item["role"]) for item in pending.json()] == [("invitee@example.com", "admin")]

    # Re-inviting replaced the link, so the first one no longer works.
    assert accept(client, invitee_token, invitation_token(first)).status_code == 404

    revoked = client.delete(
        f"/api/v1/workspaces/{workspace_id}/invitations/{second.json()['id']}", headers=auth_header(owner_token)
    )
    assert revoked.status_code == 204
    assert client.get(f"/api/v1/workspaces/{workspace_id}/invitations", headers=auth_header(owner_token)).json() == []
    assert accept(client, invitee_token, invitation_token(second)).status_code == 410


def test_cannot_invite_existing_member_or_into_personal_workspace(client: TestClient) -> None:
    owner_token = register(client, "solo@example.com", "Solo")
    workspace_id = create_organization(client, owner_token, "solo-team")

    assert invite(client, owner_token, workspace_id, "solo@example.com").status_code == 409
    assert invite(client, owner_token, workspace_id, "not-an-email").status_code == 422

    personal_id = next(
        item["workspace"]["id"]
        for item in client.get("/api/v1/workspaces", headers=auth_header(owner_token)).json()
        if item["workspace"]["type"] == "personal"
    )
    assert invite(client, owner_token, personal_id, "friend@example.com").status_code == 422


def test_member_cannot_invite(client: TestClient) -> None:
    owner_token = register(client, "own@example.com", "Owner")
    member_token = register(client, "mem@example.com", "Member")
    workspace_id = create_organization(client, owner_token, "member-team")
    assert accept(client, member_token, invitation_token(invite(client, owner_token, workspace_id, "mem@example.com"))).status_code == 200

    assert invite(client, member_token, workspace_id, "friend@example.com").status_code == 403
    assert client.get(f"/api/v1/workspaces/{workspace_id}/invitations", headers=auth_header(member_token)).status_code == 403
