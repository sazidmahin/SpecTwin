import json
from collections.abc import Generator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import LlmCall
from app.main import app
from app.services.llm_service import LlmResponse
from app.services.ollama_service import OllamaClient

TASK = (
    "A library has many books. Each book has a title and an ISBN. A member can borrow up to five books. "
    "A librarian is a kind of staff member."
)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
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


def register(client: TestClient, email: str = "modeler@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "full_name": "Modeler User"},
    )
    assert response.status_code == 202
    verification = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "code": response.json()["verification_code"]},
    )
    assert verification.status_code == 200
    return verification.json()["access_token"]


def setup_project(client: TestClient, token: str) -> tuple[str, str]:
    workspace_id = client.get("/api/v1/workspaces", headers=auth_header(token)).json()[0]["workspace"]["id"]
    project = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=auth_header(token),
        json={"name": "OOP Tasks", "description": None},
    )
    assert project.status_code == 201
    return workspace_id, project.json()["id"]


def test_rule_based_mode_needs_no_project_and_explains_itself(client: TestClient) -> None:
    token = register(client)
    workspace_id, _ = setup_project(client, token)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/class-modeler/generate",
        headers=auth_header(token),
        json={"text": TASK, "mode": "rule_based"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "rule_based"
    names = {cls["name"] for cls in body["model"]["classes"]}
    assert {"Book", "Member", "Librarian", "StaffMember", "Library"} <= names
    assert body["validation"]["valid"] is True
    assert body["drawioXml"].startswith("<mxfile")
    assert body["analysis"]["sentences"] and body["analysis"]["nouns"] and body["analysis"]["verbs"]


def test_rejects_empty_text_and_unknown_mode(client: TestClient) -> None:
    token = register(client)
    workspace_id, _ = setup_project(client, token)
    url = f"/api/v1/workspaces/{workspace_id}/class-modeler/generate"

    assert client.post(url, headers=auth_header(token), json={"text": "   ", "mode": "rule_based"}).status_code == 422
    assert client.post(url, headers=auth_header(token), json={"text": TASK, "mode": "magic"}).status_code == 422


def test_llm_mode_requires_project_then_normalizes_model(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = register(client)
    workspace_id, project_id = setup_project(client, token)
    url = f"/api/v1/workspaces/{workspace_id}/class-modeler/generate"

    no_project = client.post(url, headers=auth_header(token), json={"text": TASK, "mode": "llm"})
    assert no_project.status_code == 422
    assert "project" in no_project.json()["detail"].lower()

    # Uses the user's own provider (or local Ollama): no paid plan needed.
    llm_answer = {
        "classes": [
            {"name": "Book", "attributes": [{"name": "title", "type": "String"}, "isbn: String"], "methods": []},
            {"name": "Member", "attributes": [], "methods": [
                {"name": "borrowBook", "parameters": [{"name": "book", "type": "Book"}], "returnType": "void"}
            ]},
            {"name": "Librarian", "attributes": [], "methods": ["addBook(book: Book): void"]},
            {"name": "StaffMember", "abstract": True, "attributes": [], "methods": []},
        ],
        "relationships": [
            {"from": "Member", "to": "Book", "type": "association", "label": "borrows",
             "sourceMultiplicity": "1", "targetMultiplicity": "0..5"},
            {"from": "Librarian", "to": "StaffMember", "type": "generalization"},
            {"from": "Member", "to": "Ghost", "type": "association"},
        ],
        "enums": [],
        "nouns": [{"name": "library", "decision": "rejected", "reason": "system name"}],
        "verbs": [{"verb": "borrow", "subject": "Member", "object": "Book", "assignedTo": "Member", "method": "borrowBook(book)"}],
    }
    monkeypatch.setattr(OllamaClient, "validate_configuration", lambda self: None)

    def fake_generate(self: OllamaClient, request):
        assert "REQUIREMENT_TEXT_START" in request.prompt and TASK in request.prompt
        content = json.dumps(llm_answer)
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=10, completion_tokens=10)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)

    response = client.post(url, headers=auth_header(token), json={"text": TASK, "mode": "llm", "project_id": project_id})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "llm" and body["provider"] == "ollama"
    classes = {cls["name"]: cls for cls in body["model"]["classes"]}
    assert classes["StaffMember"]["stereotype"] == "abstract"
    assert [attr["name"] for attr in classes["Book"]["attributes"]] == ["title", "isbn"]
    assert classes["Librarian"]["methods"][0]["parameters"] == [{"name": "book", "type": "Book"}]
    types = sorted(rel["type"] for rel in body["model"]["relationships"])
    assert types == ["association", "inheritance"]  # the edge to an unknown class is dropped
    assert body["validation"]["valid"] is True
    assert body["analysis"]["nouns"][0]["decision"] == "rejected"
    assert db_session.scalar(select(LlmCall).where(LlmCall.project_id == UUID(project_id))) is not None


def test_explicit_ollama_provider_model_choice_and_model_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = register(client, "ollama-modeler@example.com")
    workspace_id, project_id = setup_project(client, token)
    base = f"/api/v1/workspaces/{workspace_id}/class-modeler"
    monkeypatch.setattr(OllamaClient, "available_models", lambda self: ["llama3.2:1b", "llama3.2", "qwen2.5:7b", "qwen2.5"])

    models = client.get(f"{base}/ollama-models", headers=auth_header(token))
    assert models.status_code == 200
    assert models.json()["reachable"] is True
    assert models.json()["installed"] == ["llama3.2:1b", "qwen2.5:7b"]

    seen: dict[str, str] = {}

    def fake_generate(self: OllamaClient, request):
        seen["model"] = self.model_name
        seen["prompt"] = request.prompt
        content = json.dumps({
            "classes": [
                {"name": "Book", "attributes": ["title: String", "isbn: String"], "methods": []},
                {"name": "Member", "attributes": ["name: String"], "methods": ["borrow(book: Book): void"]},
            ],
            "relationships": [{"from": "Member", "to": "Book", "type": "association", "label": "borrows", "targetMultiplicity": "0..5"}],
        })
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=5, completion_tokens=5)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)
    response = client.post(
        f"{base}/generate",
        headers=auth_header(token),
        json={"text": TASK, "mode": "llm", "project_id": project_id, "llm_provider": "ollama", "model_name": "qwen2.5:7b"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "ollama" and body["modelName"] == "qwen2.5:7b"
    assert seen["model"] == "qwen2.5:7b"
    assert '"attributes": ["title: String"' in seen["prompt"]  # the short Ollama contract
    member = next(cls for cls in body["model"]["classes"] if cls["name"] == "Member")
    assert member["methods"][0]["parameters"] == [{"name": "book", "type": "Book"}]
    assert body["model"]["relationships"][0]["targetMultiplicity"] == "0..5"

    missing = client.post(
        f"{base}/generate",
        headers=auth_header(token),
        json={"text": TASK, "mode": "llm", "project_id": project_id, "llm_provider": "ollama", "model_name": "mistral:latest"},
    )
    assert missing.status_code == 422
    assert "ollama pull mistral:latest" in missing.json()["detail"]

    from app.core.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    hosted = client.post(
        f"{base}/generate",
        headers=auth_header(token),
        json={"text": TASK, "mode": "llm", "project_id": project_id, "llm_provider": "ai"},
    )
    assert hosted.status_code == 422
    assert "AI generation" in hosted.json()["detail"]
    assert "openrouter" not in hosted.text.lower()

    # The user's own provider key is still a choice of its own, next to the
    # local model and the platform's hosted engine.
    byok = client.post(
        f"{base}/generate",
        headers=auth_header(token),
        json={"text": TASK, "mode": "llm", "project_id": project_id, "llm_provider": "byok"},
    )
    assert byok.status_code == 422
    assert "AI Settings" in byok.json()["detail"]


def test_ollama_models_reports_unreachable_server(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.llm_service import LlmConfigurationError

    token = register(client, "ollama-down@example.com")
    workspace_id, _ = setup_project(client, token)

    def down(self):
        raise LlmConfigurationError("Cannot reach the Ollama server at http://localhost:11434.")

    monkeypatch.setattr(OllamaClient, "available_models", down)
    body = client.get(f"/api/v1/workspaces/{workspace_id}/class-modeler/ollama-models", headers=auth_header(token)).json()
    assert body["reachable"] is False
    assert "Cannot reach" in body["error"]
    assert body["suggested"]


def test_ai_generation_mode_is_its_own_engine(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    from app.services.hosted_ai_service import HostedAiClient

    token = register(client, "ai-modeler@example.com")
    workspace_id, project_id = setup_project(client, token)
    base = f"/api/v1/workspaces/{workspace_id}/class-modeler"
    monkeypatch.setattr(settings, "openrouter_api_key", "platform-key")
    monkeypatch.setattr(settings, "openrouter_model", "vendor/model-a")

    def fake_generate(self: HostedAiClient, request):
        content = json.dumps({
            "classes": [
                {"name": "Book", "attributes": [{"name": "title", "type": "String"}], "methods": []},
                {"name": "Member", "attributes": [{"name": "name", "type": "String"}], "methods": []},
            ],
            "relationships": [{"from": "Member", "to": "Book", "type": "association", "label": "borrows"}],
        })
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=5, completion_tokens=5)

    monkeypatch.setattr(HostedAiClient, "generate", fake_generate)
    response = client.post(
        f"{base}/generate",
        headers=auth_header(token),
        json={"text": TASK, "mode": "ai", "project_id": project_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "ai" and body["provider"] == "ai"
    assert body["modelName"] is None
    assert {cls["name"] for cls in body["model"]["classes"]} == {"Book", "Member"}
    assert "openrouter" not in response.text.lower()


def test_a_fixed_class_model_is_remembered_and_steers_the_next_generation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Class Modeler is stateless, so a user's fix used to vanish with the
    page. Now it is stored against the requirement text and fed back the next
    time that text is modelled."""
    from app.core.config import settings
    from app.services import rag_service
    from app.services.hosted_ai_service import HostedAiClient

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_embedder", "lexical")
    monkeypatch.setattr(settings, "openrouter_api_key", "platform-key")
    monkeypatch.setattr(settings, "openrouter_model", "vendor/model-a")
    monkeypatch.setattr(rag_service, "_vector_store", rag_service.InMemoryVectorStore())

    prompts: list[str] = []
    generated = {
        "classes": [
            {"name": "Book", "attributes": [{"name": "title", "type": "String"}], "methods": []},
            {"name": "Member", "attributes": [{"name": "name", "type": "String"}], "methods": []},
        ],
        "relationships": [{"from": "Member", "to": "Book", "type": "association", "label": "borrows"}],
    }

    def fake_generate(self: HostedAiClient, request):
        prompts.append(request.prompt)
        content = json.dumps(generated)
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=5, completion_tokens=5)

    monkeypatch.setattr(HostedAiClient, "generate", fake_generate)

    token = register(client, "modeler-memory@example.com")
    workspace_id, project_id = setup_project(client, token)
    base = f"/api/v1/workspaces/{workspace_id}/class-modeler"
    body = {"text": TASK, "mode": "ai", "project_id": project_id}

    first = client.post(f"{base}/generate", headers=auth_header(token), json=body)
    assert first.status_code == 200, first.text
    # Nothing has been corrected yet, so nothing is quoted back at the model.
    assert "youIncorrectlyProduced" not in prompts[0]

    wrong_model = first.json()["model"]
    fixed_model = {
        **wrong_model,
        "classes": [
            *wrong_model["classes"],
            {"id": "c_librarian", "name": "Librarian", "stereotype": "entity", "attributes": [], "methods": [], "sourceSentences": []},
        ],
    }
    remembered = client.post(
        f"{base}/corrections",
        headers=auth_header(token),
        json={
            "text": TASK,
            "project_id": project_id,
            "generation_mode": "ai",
            "wrong_model": wrong_model,
            "corrected_model": fixed_model,
        },
    )
    assert remembered.status_code == 200, remembered.text
    assert remembered.json() == {"remembered": True}

    second = client.post(f"{base}/generate", headers=auth_header(token), json=body)
    assert second.status_code == 200, second.text
    assert "youIncorrectlyProduced" in prompts[1]
    assert "Librarian" in prompts[1]


def test_correction_memory_is_honest_about_not_storing_anything(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Off by default, and a fix that changed nothing is not a fix. The endpoint
    reports that rather than letting the UI claim the engine learned."""
    from app.core.config import settings

    token = register(client, "modeler-memory-off@example.com")
    workspace_id, project_id = setup_project(client, token)
    base = f"/api/v1/workspaces/{workspace_id}/class-modeler"
    model = {"classes": [{"name": "Book", "attributes": [], "methods": []}], "relationships": [], "enums": []}
    payload = {
        "text": TASK,
        "project_id": project_id,
        "generation_mode": "ai",
        "wrong_model": model,
        "corrected_model": {**model, "classes": [{"name": "Novel", "attributes": [], "methods": []}]},
    }

    off = client.post(f"{base}/corrections", headers=auth_header(token), json=payload)
    assert off.status_code == 200, off.text
    assert off.json() == {"remembered": False}

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_embedder", "lexical")
    unchanged = client.post(
        f"{base}/corrections", headers=auth_header(token), json={**payload, "corrected_model": model}
    )
    assert unchanged.json() == {"remembered": False}

    # The rule engine is deterministic, so there is nothing it could learn.
    rule_based = client.post(f"{base}/corrections", headers=auth_header(token), json={**payload, "generation_mode": "rule_based"})
    assert rule_based.status_code == 422
    assert "AI engine" in rule_based.json()["detail"]
