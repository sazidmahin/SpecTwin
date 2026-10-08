from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import verify_password
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import User, Workspace, WorkspaceMember
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


def register_and_verify(client: TestClient, email: str, full_name: str) -> str:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "full_name": full_name},
    )
    assert register_response.status_code == 202
    code = register_response.json()["verification_code"]
    assert code

    verify_response = client.post(
        "/api/v1/auth/verify-email", json={"email": email, "code": code}
    )
    assert verify_response.status_code == 200
    return verify_response.json()["access_token"]


def test_register_creates_inactive_user_personal_workspace_and_owner_membership(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Ada@example.com",
            "password": "correct-horse",
            "full_name": "Ada Lovelace",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["message"] == "Verification code sent to email"
    assert body["verification_code"]

    user = db_session.scalar(select(User).where(User.email == "ada@example.com"))
    assert user is not None
    assert user.password_hash != "correct-horse"
    assert user.status == "inactive"
    assert user.email_verified is False
    assert user.email_verification_code_hash is not None

    workspace = db_session.scalar(select(Workspace).where(Workspace.owner_user_id == user.id))
    assert workspace is not None
    assert workspace.type == "personal"
    assert workspace.status == "active"

    membership = db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    assert membership is not None
    assert membership.role == "owner"
    assert membership.status == "active"


def test_verify_email_activates_user_and_returns_token(
    client: TestClient, db_session: Session
) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "verify@example.com",
            "password": "correct-horse",
            "full_name": "Verify User",
        },
    )
    code = register_response.json()["verification_code"]

    verify_response = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "VERIFY@example.com", "code": code},
    )

    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "verify@example.com"
    assert body["user"]["status"] == "active"
    assert body["user"]["email_verified"] is True

    user = db_session.scalar(select(User).where(User.email == "verify@example.com"))
    assert user is not None
    assert user.status == "active"
    assert user.email_verified is True
    assert user.email_verification_code_hash is None


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {
        "email": "ada@example.com",
        "password": "correct-horse",
        "full_name": "Ada Lovelace",
    }

    assert client.post("/api/v1/auth/register", json=payload).status_code == 202
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409


def test_login_requires_verified_email(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pending@example.com",
            "password": "correct-horse",
            "full_name": "Pending User",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "pending@example.com", "password": "correct-horse"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Email verification required"


def test_login_and_me_return_current_user_workspaces(client: TestClient) -> None:
    access_token = register_and_verify(client, "grace@example.com", "Grace Hopper")

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "GRACE@example.com", "password": "correct-horse"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["user"]["email"] == "grace@example.com"
    assert len(body["workspaces"]) == 1
    assert body["workspaces"][0]["role"] == "owner"
    assert body["workspaces"][0]["workspace"]["type"] == "personal"


def test_login_rejects_bad_password(client: TestClient) -> None:
    register_and_verify(client, "bad-password@example.com", "Bad Password")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "bad-password@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_logout_requires_valid_bearer_token(client: TestClient) -> None:
    token = register_and_verify(client, "logout@example.com", "Logout User")

    response = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}


def test_resend_verification_code_returns_new_code_after_cooldown(
    client: TestClient, db_session: Session
) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "resend@example.com",
            "password": "correct-horse",
            "full_name": "Resend User",
        },
    )
    original_code = register_response.json()["verification_code"]

    user = db_session.scalar(select(User).where(User.email == "resend@example.com"))
    assert user is not None
    user.email_verification_sent_at = None
    db_session.commit()

    resend_response = client.post(
        "/api/v1/auth/resend-verification-code", json={"email": "resend@example.com"}
    )

    assert resend_response.status_code == 200
    new_code = resend_response.json()["verification_code"]
    assert new_code
    assert new_code != original_code


def test_forgot_password_and_reset_password_flow(
    client: TestClient, db_session: Session
) -> None:
    register_and_verify(client, "reset@example.com", "Reset User")

    forgot_response = client.post(
        "/api/v1/auth/forgot-password", json={"email": "RESET@example.com"}
    )

    assert forgot_response.status_code == 200
    reset_token = forgot_response.json()["reset_token"]
    assert reset_token

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "new-password"},
    )

    assert reset_response.status_code == 200
    assert reset_response.json() == {"message": "Password reset successfully"}

    user = db_session.scalar(select(User).where(User.email == "reset@example.com"))
    assert user is not None
    assert verify_password("new-password", user.password_hash)

    old_login_response = client.post(
        "/api/v1/auth/login", json={"email": "reset@example.com", "password": "old-password"}
    )
    assert old_login_response.status_code == 401

    new_login_response = client.post(
        "/api/v1/auth/login", json={"email": "reset@example.com", "password": "new-password"}
    )
    assert new_login_response.status_code == 200


def test_reset_password_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "new-password"},
    )

    assert response.status_code == 400
