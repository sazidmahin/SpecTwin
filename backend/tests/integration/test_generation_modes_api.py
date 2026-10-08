import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import UserAiProviderCredential
from app.main import app
from app.services.llm_service import LlmResponse
from app.services.ollama_service import OllamaClient


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = testing_session()
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


def register(client: TestClient, email: str = "pipeline@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse", "full_name": "Pipeline User"},
    )
    assert response.status_code == 202
    verification = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "code": response.json()["verification_code"]},
    )
    assert verification.status_code == 200
    return verification.json()["access_token"]


def setup_project(client: TestClient, token: str) -> tuple[str, str]:
    workspaces = client.get("/api/v1/workspaces", headers=auth_header(token))
    workspace_id = workspaces.json()[0]["workspace"]["id"]
    project = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        headers=auth_header(token),
        json={"name": "Generation Modes", "description": None},
    )
    assert project.status_code == 201
    return workspace_id, project.json()["id"]


def pipeline_url(workspace_id: str, project_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/projects/{project_id}/generation-pipelines"


def approve_and_proceed(
    client: TestClient,
    token: str,
    base_url: str,
    run: dict,
) -> dict:
    current = next(stage for stage in run["stages"] if stage["stage_name"] == run["current_stage"])
    response = client.post(
        f"{base_url}/{run['id']}/stages/{run['current_stage']}/approve",
        headers=auth_header(token),
        json={"version_number": current["version_number"], "proceed": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_rule_based_pipeline_is_editable_and_xml_is_deterministic(client: TestClient) -> None:
    token = register(client)
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)
    response = client.post(
        base_url,
        headers=auth_header(token),
        json={
            "title": "Order management",
            "raw_text": "Administrator can create Order.",
            "generation_mode": "rule_based",
        },
    )
    assert response.status_code == 201, response.text
    run = response.json()

    for expected_stage in ("clarifications", "final-story", "requirements", "class-model"):
        run = approve_and_proceed(client, token, base_url, run)
        assert run["current_stage"] == expected_stage

    class_stage = next(stage for stage in run["stages"] if stage["stage_name"] == "class-model")
    add_response = client.post(
        f"{base_url}/{run['id']}/class-model/classes",
        headers=auth_header(token),
        json={
            "expected_version": class_stage["version_number"],
            "data": {"id": "class_audit_log", "name": "AuditLog"},
        },
    )
    assert add_response.status_code == 200, add_response.text
    assert any(item["name"] == "AuditLog" for item in add_response.json()["payload"]["classes"])

    run = client.get(f"{base_url}/{run['id']}", headers=auth_header(token)).json()
    run = approve_and_proceed(client, token, base_url, run)
    assert run["current_stage"] == "xml"
    xml_stage = next(stage for stage in run["stages"] if stage["stage_name"] == "xml")
    assert xml_stage["payload"]["validation"]["valid"] is True
    assert "AuditLog" in xml_stage["payload"]["xml"]

    reopen = client.post(
        f"{base_url}/{run['id']}/stages/class-model/reopen",
        headers=auth_header(token),
    )
    assert reopen.status_code == 200, reopen.text
    refreshed = client.get(f"{base_url}/{run['id']}", headers=auth_header(token)).json()
    statuses = {stage["stage_name"]: stage["status"] for stage in refreshed["stages"]}
    assert statuses["class-model"] == "ready_for_review"
    assert statuses["xml"] == "stale"


_OLLAMA_NON_JSON_RESPONSES = {
    "pipeline_clarifications_ollama_questions": (
        "Sentences: A customer can place an order. An admin can approve an order.\n"
        "What is the maximum number of items per order?\n"
        "How long should an unapproved order remain pending?\n"
        "The order total must be calculated automatically."
    ),
    "pipeline_clarifications_answer_batch": "1. Ten items\n2. Ten items",
    "pipeline_final-story_ollama_independent": (
        "A customer places an order for one or more products.\n"
        "An admin reviews and approves pending orders.\n"
        "The system automatically calculates the order total."
    ),
    "pipeline_requirements_ollama_independent": (
        "The system shall allow a customer to place an order.\n"
        "The system shall allow an admin to approve an order.\n"
        "The system shall respond within two seconds (performance)."
    ),
    "pipeline_class-model_ollama_independent": (
        "The domain centers on a Customer who places an Order containing OrderItem "
        "entries, and an Admin who approves the Order."
    ),
}


def test_ollama_pipeline_falls_back_to_text_extraction_except_class_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Freeform-text stages (clarifications/final-story/requirements) still produce
    a usable payload verbatim from the model's own prose when it ignores the JSON
    contract - this is the normal case for small local models, not an edge case.
    class-model is different: attributes/methods/relationships cannot be honestly
    recovered from flat text, so guessing classes via a capitalized-word regex
    would fabricate wrong entities. That stage must fail loudly instead so the run
    surfaces as failed and can be regenerated (see _fallback_stage_payload).
    """
    monkeypatch.setattr(OllamaClient, "validate_configuration", lambda self: None)

    def fake_generate(self: OllamaClient, request):
        content = _OLLAMA_NON_JSON_RESPONSES.get(request.purpose, "No structured answer available.")
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)

    token = register(client, "ollama@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)

    created = client.post(
        base_url,
        headers=auth_header(token),
        json={
            "title": "Order management",
            "raw_text": "A customer can place an order. An admin can approve an order.",
            "generation_mode": "ollama",
        },
    )
    assert created.status_code == 201, created.text
    run = created.json()

    # --- input: approving it generates the clarifications stage ---
    run = approve_and_proceed(client, token, base_url, run)
    assert run["current_stage"] == "clarifications"

    # --- clarifications: fallback-extracted questions, each auto-answered ---
    clarifications = next(stage for stage in run["stages"] if stage["stage_name"] == "clarifications")
    questions = clarifications["payload"]["clarificationQuestions"]
    assert len(questions) >= 1
    for question in questions:
        assert isinstance(question["id"], str) and question["id"]
        assert isinstance(question["text"], str) and question["text"]
        assert isinstance(question["category"], str) and question["category"]
    answers = clarifications["payload"]["answers"]
    assert len(answers) == len(questions)
    for answer in answers:
        assert answer.get("answerText") == "Ten items"

    # --- approve clarifications: generates final-story ---
    run = approve_and_proceed(client, token, base_url, run)
    assert run["current_stage"] == "final-story"
    final_story = next(stage for stage in run["stages"] if stage["stage_name"] == "final-story")
    sections = final_story["payload"]["atomicStorySections"]
    assert len(sections) == 3
    for section in sections:
        assert isinstance(section["id"], str) and section["id"]
        assert isinstance(section["normalizedSentence"], str) and section["normalizedSentence"]
    assert isinstance(final_story["payload"]["warnings"], list)

    # --- approve final-story: generates requirements ---
    run = approve_and_proceed(client, token, base_url, run)
    assert run["current_stage"] == "requirements"
    requirements_stage = next(stage for stage in run["stages"] if stage["stage_name"] == "requirements")
    requirements = requirements_stage["payload"]["requirements"]
    assert len(requirements) == 3
    types = {requirement["requirementType"] for requirement in requirements}
    assert types == {"functional", "non_functional"}
    for requirement in requirements:
        assert isinstance(requirement["requirementId"], str) and requirement["requirementId"]
        assert isinstance(requirement["statement"], str) and requirement["statement"]
        assert requirement["enabled"] is True

    # --- approve requirements: class-model generation must fail loudly instead of
    # fabricating classes from a capitalized-word regex over free text ---
    current = next(stage for stage in run["stages"] if stage["stage_name"] == run["current_stage"])
    response = client.post(
        f"{base_url}/{run['id']}/stages/{run['current_stage']}/approve",
        headers=auth_header(token),
        json={"version_number": current["version_number"], "proceed": True},
    )
    assert response.status_code == 409, response.text
    assert "class-model" in response.json()["detail"].lower()

    run_after = client.get(f"{base_url}/{run['id']}", headers=auth_header(token)).json()
    assert run_after["status"] == "failed"
    assert run_after["current_stage"] == "requirements"


_OLLAMA_CLASS_MODEL_RESPONSES = {
    "pipeline_clarifications_ollama_questions": '{"clarificationQuestions": []}',
    "pipeline_final-story_ollama_independent": (
        '{"atomicStorySections": [{"id": "s1", "normalizedSentence": "stub"}]}'
    ),
    "pipeline_requirements_ollama_independent": (
        '{"requirements": [{"requirementId": "REQ-1", "requirementType": "functional", '
        '"statement": "stub", "actor": "User", "action": "act", "object": "Thing", "enabled": true}]}'
    ),
    # A small model restarting the JSON object per class instead of accumulating
    # into one array - the exact shape that made json.loads silently keep only
    # the last "classes" key and discard the other two (see _merge_duplicate_json_keys).
    "pipeline_class-model_ollama_classes": (
        '{"classes": [{"name": "Patient", "fields": ["age"], "methods": ["register"]}], '
        '"classes": [{"name": "Doctor", "fields": ["specialty"], "methods": ["viewSchedule"]}], '
        '"classes": [{"name": "Receptionist", "fields": [], "methods": ["checkIn"]}]}'
    ),
    "pipeline_class-model_ollama_relationships": (
        '{"relationships": [{"from": "Patient", "to": "Doctor", "type": "has many", "label": "books with"}]}'
    ),
}


def test_ollama_class_model_recovers_duplicate_keys_and_gets_own_relationships_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class-model is generated as two focused Ollama calls (classes, then
    relationships against that settled class list) instead of one combined ask -
    see _generate_ollama_class_model. This proves both halves of that fix: (1) a
    response that restarts the JSON object per class (three separate top-level
    "classes" keys) must not silently lose two of the three classes to Python's
    default last-key-wins JSON parsing, and (2) relationships come from their own
    dedicated call and reference the classes that were actually kept.
    """
    monkeypatch.setattr(OllamaClient, "validate_configuration", lambda self: None)

    def fake_generate(self: OllamaClient, request):
        content = _OLLAMA_CLASS_MODEL_RESPONSES.get(request.purpose, "{}")
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)

    token = register(client, "ollama-classmodel@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)

    created = client.post(
        base_url,
        headers=auth_header(token),
        json={
            "title": "Hospital",
            "raw_text": "Patients book appointments with doctors. Receptionists check patients in.",
            "generation_mode": "ollama",
        },
    )
    assert created.status_code == 201, created.text
    run = created.json()

    run = approve_and_proceed(client, token, base_url, run)  # -> clarifications
    run = approve_and_proceed(client, token, base_url, run)  # -> final-story
    run = approve_and_proceed(client, token, base_url, run)  # -> requirements
    run = approve_and_proceed(client, token, base_url, run)  # -> class-model

    assert run["current_stage"] == "class-model"
    class_model_stage = next(stage for stage in run["stages"] if stage["stage_name"] == "class-model")
    classes = class_model_stage["payload"]["classes"]
    class_names = {item["name"] for item in classes}
    assert class_names == {"Patient", "Doctor", "Receptionist"}, (
        "all three classes must survive, not just the last duplicate 'classes' key"
    )
    for item in classes:
        assert isinstance(item["id"], str) and item["id"]
        assert isinstance(item["attributes"], list)
        assert isinstance(item["methods"], list)

    relationships = class_model_stage["payload"]["relationships"]
    assert len(relationships) == 1
    relationship = relationships[0]
    patient_id = next(item["id"] for item in classes if item["name"] == "Patient")
    doctor_id = next(item["id"] for item in classes if item["name"] == "Doctor")
    assert relationship["sourceClassId"] == patient_id
    assert relationship["targetClassId"] == doctor_id
    assert relationship["label"] == "books with"
    assert relationship["type"] == "association"  # "has many" isn't a canonical type - safe default, not a guess

    # --- approve class-model: xml renders successfully from this data ---
    run = approve_and_proceed(client, token, base_url, run)
    assert run["current_stage"] == "xml"
    xml_stage = next(stage for stage in run["stages"] if stage["stage_name"] == "xml")
    assert xml_stage["payload"]["validation"]["valid"] is True
    for name in class_names:
        assert name in xml_stage["payload"]["xml"]


def test_rag_correction_memory_feeds_past_mistakes_back_into_the_prompt(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Correcting an Ollama-authored final-story draft on one run should surface
    that correction as pastCorrections context the next time final-story is
    generated for a similar input - and must not appear before any correction
    exists yet. Gated entirely by RAG_ENABLED; embeddings are mocked to a fixed
    vector so retrieval is deterministic regardless of exact wording.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(OllamaClient, "validate_configuration", lambda self: None)
    monkeypatch.setattr(OllamaClient, "embed", lambda self, text, model=None: [1.0, 0.0, 0.0])

    final_story_prompts: list[str] = []
    original_final_story = {
        "originalText": "x",
        "normalizedSentences": [],
        "atomicStorySections": [{"id": "s1", "normalizedSentence": "Original bad content."}],
        "appliedClarificationAnswers": [],
        "unresolvedFields": [],
        "warnings": [],
        "extractionMetadata": {},
    }

    def fake_generate(self: OllamaClient, request):
        if request.purpose == "pipeline_clarifications_ollama_questions":
            content = '{"clarificationQuestions": []}'
        elif request.purpose == "pipeline_final-story_ollama_independent":
            final_story_prompts.append(request.prompt)
            content = json.dumps(original_final_story)
        else:
            content = "{}"
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)

    token = register(client, "rag@example.com")
    workspace_id, _ = setup_project(client, token)

    def run_through_final_story(raw_text: str) -> dict:
        project = client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            headers=auth_header(token),
            json={"name": f"RAG project {raw_text[:10]}", "description": None},
        )
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]
        base_url = pipeline_url(workspace_id, project_id)
        created = client.post(
            base_url,
            headers=auth_header(token),
            json={"title": "RAG test", "raw_text": raw_text, "generation_mode": "ollama"},
        )
        assert created.status_code == 201, created.text
        run = created.json()
        run = approve_and_proceed(client, token, base_url, run)  # input -> clarifications
        run = approve_and_proceed(client, token, base_url, run)  # clarifications -> final-story
        assert run["current_stage"] == "final-story"
        return {"token": token, "base_url": base_url, "run": run}

    # --- Run A: no correction exists yet, so no pastCorrections should appear ---
    ctx_a = run_through_final_story("A customer can place an order.")
    assert len(final_story_prompts) == 1
    # The static instruction text always mentions the word "pastCorrections" (explaining
    # what it means if present); what must NOT appear yet is actual correction data.
    assert '"pastCorrections":' not in final_story_prompts[0]

    final_story_a = next(stage for stage in ctx_a["run"]["stages"] if stage["stage_name"] == "final-story")
    corrected_payload = {**original_final_story, "atomicStorySections": [{"id": "s1", "normalizedSentence": "Corrected content."}]}
    save = client.post(
        f"{ctx_a['base_url']}/{ctx_a['run']['id']}/stages/final-story/revisions",
        headers=auth_header(ctx_a["token"]),
        json={"payload": corrected_payload, "expected_version": final_story_a["version_number"]},
    )
    assert save.status_code == 200, save.text

    # --- Run B: a correction now exists and should surface as pastCorrections ---
    run_through_final_story("An admin can approve an order.")
    assert len(final_story_prompts) == 2
    assert '"pastCorrections":' in final_story_prompts[1]
    assert "Original bad content." in final_story_prompts[1]
    assert "Corrected content." in final_story_prompts[1]


def test_ai_settings_encrypt_key_and_gate_ai_gen(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register(client, "byok@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)

    providers = client.get("/api/v1/users/me/ai-settings/providers", headers=auth_header(token))
    assert providers.status_code == 200, providers.text
    openai = next(provider for provider in providers.json() if provider["provider"] == "openai")
    assert {"gpt-5.6", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini"}.issubset(openai["models"])

    blocked = client.post(
        base_url,
        headers=auth_header(token),
        json={"title": "BYOK", "raw_text": "User can create Order.", "generation_mode": "byok"},
    )
    assert blocked.status_code == 422

    api_key = "sk-secret-value-1234"
    saved = client.put(
        "/api/v1/users/me/ai-settings/credentials/openai",
        headers=auth_header(token),
        json={"api_key": api_key, "selected_model": "gpt-4o-mini", "is_default": True},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["key_last_four"] == "1234"
    assert api_key not in saved.text
    stored = db_session.scalar(select(UserAiProviderCredential))
    assert stored is not None
    assert stored.encrypted_api_key != api_key
    assert api_key not in stored.encrypted_api_key

    monkeypatch.setattr(
        "app.services.ai_settings_service._fetch_provider_models",
        lambda provider, key: ["gpt-4.1", "gpt-4.1-nano"],
    )
    models = client.get(
        "/api/v1/users/me/ai-settings/credentials/openai/models",
        headers=auth_header(token),
    )
    assert models.status_code == 200, models.text
    assert models.json() == ["gpt-4.1", "gpt-4.1-nano"]

    custom_model = "gpt-5.4"
    updated = client.patch(
        "/api/v1/users/me/ai-settings/credentials/openai",
        headers=auth_header(token),
        json={"selected_model": custom_model},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["selected_model"] == custom_model

    class HealthyClient:
        provider = "openai"
        model_name = "gpt-4o-mini"

        def generate(self, request):
            return LlmResponse(
                content="OK",
                response_payload={"content": "OK"},
                prompt_tokens=1,
                completion_tokens=1,
            )

    monkeypatch.setattr(
        "app.services.ai_settings_service.build_client_for_credential",
        lambda credential: HealthyClient(),
    )
    tested = client.post(
        "/api/v1/users/me/ai-settings/credentials/openai/test",
        headers=auth_header(token),
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["status"] == "valid"

    created = client.post(
        base_url,
        headers=auth_header(token),
        json={"title": "BYOK", "raw_text": "User can create Order.", "generation_mode": "byok"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["generation_mode"] == "byok"
    assert created.json()["provider"] == "openai"
    assert created.json()["model_name"] == custom_model
    assert api_key not in created.text


def test_completed_pipeline_publishes_srs_document_and_diagram(client: TestClient) -> None:
    token = register(client, "publish@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)
    run = client.post(
        base_url,
        headers=auth_header(token),
        json={
            "title": "Library system",
            "raw_text": (
                "A librarian can add books. A member can borrow a book. "
                "Each book has a title and an ISBN. The system must respond within 2 seconds."
            ),
            "generation_mode": "rule_based",
        },
    ).json()
    assert run["srs_document_id"] is None

    for _ in range(6):
        run = approve_and_proceed(client, token, base_url, run)
    assert run["status"] == "completed"
    document_id = run["srs_document_id"]
    assert document_id

    srs_url = f"/api/v1/workspaces/{workspace_id}/projects/{project_id}/srs"
    document = client.get(f"{srs_url}/{document_id}", headers=auth_header(token)).json()
    assert document["pipeline_run_id"] == run["id"]
    markdown = document["content_markdown"]
    for heading in ("# Library system", "## 1. Introduction", "### 3.1 Functional requirements", "## 4. Domain Model"):
        assert heading in markdown
    assert "The system shall" in markdown
    assert document["content_json"]["requirements"]

    diagram = client.get(
        f"/api/v1/workspaces/{workspace_id}/projects/{project_id}/diagrams/{document['diagram_id']}",
        headers=auth_header(token),
    )
    assert diagram.status_code == 200
    assert diagram.json()["source"] == "generated"
    assert "<mxfile" in diagram.json()["current"]["drawio_xml"]

    workspace_diagrams = client.get(f"/api/v1/workspaces/{workspace_id}/diagrams", headers=auth_header(token)).json()
    assert [item["id"] for item in workspace_diagrams] == [document["diagram_id"]]

    workspace_docs = client.get(f"/api/v1/workspaces/{workspace_id}/srs-documents", headers=auth_header(token)).json()
    assert [item["id"] for item in workspace_docs] == [document_id]

    runs = client.get(f"/api/v1/workspaces/{workspace_id}/generation-pipelines", headers=auth_header(token)).json()
    assert runs[0]["id"] == run["id"]
    assert runs[0]["project_name"] == "Generation Modes"
    assert runs[0]["srs_document_id"] == document_id
    project_runs = client.get(base_url, headers=auth_header(token)).json()
    assert "stages" not in project_runs[0]

    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search", params={"q": "librar"}, headers=auth_header(token)
    ).json()
    assert [item["id"] for item in search["documents"]] == [document_id]
    assert [item["id"] for item in search["runs"]] == [run["id"]]
    assert search["diagrams"][0]["id"] == document["diagram_id"]

    edited = client.patch(
        f"{srs_url}/{document_id}",
        headers=auth_header(token),
        json={"title": "Library SRS", "content_markdown": "# Library SRS\n\nEdited."},
    )
    assert edited.status_code == 200
    assert edited.json()["content_json"]["editedManually"] is True
    exported = client.get(f"{srs_url}/{document_id}/export", headers=auth_header(token))
    assert exported.status_code == 200
    assert exported.text == "# Library SRS\n\nEdited."

    renamed = client.patch(f"{base_url}/{run['id']}", headers=auth_header(token), json={"title": "Renamed run"})
    assert renamed.json()["title"] == "Renamed run"
    assert client.delete(f"{base_url}/{run['id']}", headers=auth_header(token)).status_code == 204
    assert client.get(f"{base_url}/{run['id']}", headers=auth_header(token)).status_code == 404
    # Deleting the run keeps the published document.
    assert client.get(f"{srs_url}/{document_id}", headers=auth_header(token)).status_code == 200

    assert client.delete(f"{srs_url}/{document_id}", headers=auth_header(token)).status_code == 204
    assert client.get(srs_url, headers=auth_header(token)).json() == []


def test_reapproving_a_reopened_run_refreshes_the_same_document(client: TestClient) -> None:
    token = register(client, "republish@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)
    run = client.post(
        base_url,
        headers=auth_header(token),
        json={"title": "Orders", "raw_text": "Administrator can create Order.", "generation_mode": "rule_based"},
    ).json()
    for _ in range(6):
        run = approve_and_proceed(client, token, base_url, run)
    first_document = run["srs_document_id"]

    reopen = client.post(f"{base_url}/{run['id']}/stages/xml/reopen", headers=auth_header(token))
    assert reopen.status_code == 200
    run = client.get(f"{base_url}/{run['id']}", headers=auth_header(token)).json()
    run = approve_and_proceed(client, token, base_url, run)
    assert run["status"] == "completed"
    assert run["srs_document_id"] == first_document
    docs = client.get(f"/api/v1/workspaces/{workspace_id}/srs-documents", headers=auth_header(token)).json()
    assert len(docs) == 1


def test_ollama_pipeline_chunks_large_input_and_merges_the_answers(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A long requirement text must never be sent as one prompt bigger than the
    model's window (Ollama drops the *start* of such a prompt - the instructions).
    It is split into chunks, every call is schema-constrained with a bounded
    output budget, and the per-chunk answers are merged and deduplicated."""
    from app.core.config import settings

    monkeypatch.setattr(OllamaClient, "validate_configuration", lambda self: None)
    monkeypatch.setattr(OllamaClient, "warm_up", lambda self: None)
    requests: list = []

    def fake_generate(self: OllamaClient, request):
        requests.append(request)
        purpose = request.purpose
        if purpose == "pipeline_clarifications_ollama_questions":
            content = json.dumps({"clarificationQuestions": [
                {"text": "Who approves a loan?", "category": "missing actor", "reason": "r", "sourceSentence": "s"}
            ]})
        elif purpose == "pipeline_clarifications_answer_batch":
            content = json.dumps({"answers": [{"id": "ollama_q1", "answer": "The librarian."}]})
        elif purpose == "pipeline_final-story_ollama_independent":
            n = sum(1 for call in requests if call.purpose == purpose)
            content = json.dumps({"atomicStorySections": [
                {"normalizedSentence": f"Need {n}."}, {"normalizedSentence": "A member can borrow a book."}
            ]})
        elif purpose == "pipeline_requirements_ollama_independent":
            content = json.dumps({"requirements": [
                {"statement": "The system shall let a member borrow a book.", "requirementType": "functional", "actor": "Member"}
            ]})
        elif purpose == "pipeline_class-model_ollama_classes":
            content = json.dumps({"classes": [
                {"name": "Member", "fields": ["name"], "methods": ["borrow"]},
                {"name": "Book", "fields": ["title"], "methods": []},
            ]})
        elif purpose == "pipeline_class-model_ollama_relationships":
            content = json.dumps({"relationships": [{"from": "Member", "to": "Book", "type": "association", "label": "borrows"}]})
        else:
            content = "{}"
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)
    token = register(client, "ollama-large@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)
    paragraph = (
        "A member can borrow up to five books. A librarian adds, updates and removes books. "
        "Each branch {i} has opening hours and sends reminders two days before a loan is due. "
    )
    raw_text = "\n\n".join(paragraph.replace("{i}", str(i)) * 3 for i in range(120))  # ~70k characters
    created = client.post(
        base_url, headers=auth_header(token), json={"title": "Library", "raw_text": raw_text, "generation_mode": "ollama"}
    )
    assert created.status_code == 201, created.text
    run = created.json()
    for _ in range(4):
        run = approve_and_proceed(client, token, base_url, run)
    assert run["current_stage"] == "class-model"

    window_chars = settings.ollama_num_ctx * 3.5
    assert all(len(request.prompt) < window_chars for request in requests), "a prompt overflowed the context window"
    assert all(request.json_schema and request.max_tokens for request in requests)
    story_calls = [r for r in requests if r.purpose == "pipeline_final-story_ollama_independent"]
    assert len(story_calls) > 3  # the input was chunked...
    stages = {stage["stage_name"]: stage["payload"] for stage in run["stages"]}
    sentences = [s["normalizedSentence"] for s in stages["final-story"]["atomicStorySections"]]
    assert sentences.count("A member can borrow a book.") == 1  # ...and the answers merged without duplicates
    assert len(sentences) == len(story_calls) + 1
    # one batched call drafts every clarification answer (not one call per question)
    assert sum(1 for r in requests if r.purpose == "pipeline_clarifications_answer_batch") == 1
    assert stages["clarifications"]["answers"][0]["answerText"] == "The librarian"
    classes = {item["name"] for item in stages["class-model"]["classes"]}
    assert classes == {"Member", "Book"}
    relationship_call = next(r for r in requests if r.purpose == "pipeline_class-model_ollama_relationships")
    from_enum = relationship_call.json_schema["properties"]["relationships"]["items"]["properties"]["from"]["enum"]
    assert set(from_enum) == {"Member", "Book"}
    assert len(stages["class-model"]["relationships"]) == 1


def test_hosted_ai_mode_creates_run_without_user_key(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    token = register(client, "hosted-ai@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)
    body = {"title": "Orders", "raw_text": "A customer can place an order.", "generation_mode": "ai"}

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    assert client.get("/api/v1/users/me/ai-settings/hosted", headers=auth_header(token)).json() == {"available": False}
    unavailable = client.post(base_url, headers=auth_header(token), json=body)
    assert unavailable.status_code == 422
    assert "openrouter" not in unavailable.text.lower()

    monkeypatch.setattr(settings, "openrouter_api_key", "platform-key")
    monkeypatch.setattr(settings, "openrouter_model", "vendor/model-a")
    assert client.get("/api/v1/users/me/ai-settings/hosted", headers=auth_header(token)).json() == {"available": True}
    created = client.post(base_url, headers=auth_header(token), json=body)
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["generation_mode"] == "ai"
    assert run["provider"] == "ai"
    # The hosted model is platform-configured, so the run never carries the
    # vendor's model id to the workspace or into the published SRS document.
    assert run["model_name"] is None
    assert "vendor/model-a" not in created.text

    # A client is still resolved for the run: the configured model fills in.
    from uuid import UUID

    from app.db.models import GenerationPipelineRun
    from app.services.generation_pipeline_service import _client_for_run

    stored = db_session.get(GenerationPipelineRun, UUID(run["id"]))
    resolved, credential = _client_for_run(db_session, stored)
    assert credential is None
    assert resolved.provider == "ai" and resolved.model_name == "vendor/model-a"


def test_hosted_ai_mode_writes_a_stage_over_its_own_http_layer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end over HostedAiClient's real request/response handling (only the
    socket is faked), so the wiring from mode "ai" to a written stage is covered."""
    import io
    import json as json_module

    from app.core.config import settings
    from app.services import hosted_ai_service

    token = register(client, "hosted-ai-stage@example.com")
    workspace_id, project_id = setup_project(client, token)
    base_url = pipeline_url(workspace_id, project_id)
    monkeypatch.setattr(settings, "openrouter_api_key", "platform-key")
    monkeypatch.setattr(settings, "openrouter_model", "vendor/model-a")
    monkeypatch.setattr(settings, "openrouter_fallback_models", "")

    stage_payload = {
        "facts": [{"id": "f1", "text": "A customer places an order."}],
        "sentences": [{"id": "s1", "text": "A customer can place an order."}],
        "clarificationQuestions": [{"id": "q1", "text": "Can an order hold many products?", "status": "open"}],
    }
    requests_sent: list[dict] = []

    class _FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_urlopen(request, timeout):
        requests_sent.append({"body": json_module.loads(request.data), "headers": dict(request.headers)})
        body = {
            "model": "vendor/model-a",
            "choices": [{"message": {"content": json_module.dumps(stage_payload)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30},
        }
        return _FakeResponse(json_module.dumps(body).encode("utf-8"))

    monkeypatch.setattr(hosted_ai_service, "urlopen", fake_urlopen)

    run = client.post(
        base_url,
        headers=auth_header(token),
        json={"title": "Orders", "raw_text": "A customer can place an order.", "generation_mode": "ai"},
    ).json()
    run = approve_and_proceed(client, token, base_url, run)

    assert run["current_stage"] == "clarifications"
    stages = {stage["stage_name"]: stage["payload"] for stage in run["stages"]}
    assert stages["clarifications"]["clarificationQuestions"][0]["text"] == "Can an order hold many products?"
    # The call really went out over the hosted client, with the platform key.
    assert requests_sent and requests_sent[0]["body"]["model"] == "vendor/model-a"
    assert requests_sent[0]["headers"]["Authorization"] == "Bearer platform-key"
    # Nothing about the vendor reaches the workspace.
    assert run["model_name"] is None
    assert "vendor/model-a" not in json.dumps(run)


def test_hosted_ai_runs_also_learn_from_corrections_without_any_local_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The learning loop used to be Ollama-only, in both senses: only ollama runs
    captured corrections, and the only embedder was Ollama's. A user on the
    hosted engine installs nothing, so neither held - they got no memory at all.
    """
    from app.core.config import settings
    from app.services import rag_service
    from app.services.hosted_ai_service import HostedAiClient

    monkeypatch.setattr(settings, "rag_enabled", True)
    monkeypatch.setattr(settings, "rag_embedder", "auto")
    monkeypatch.setattr(settings, "openrouter_api_key", "platform-key")
    monkeypatch.setattr(settings, "openrouter_model", "vendor/model-a")
    # No Ollama anywhere, which is the whole point of the hosted engine.
    monkeypatch.setattr(
        OllamaClient, "embed", lambda self, text, model=None: (_ for _ in ()).throw(RuntimeError("no ollama here"))
    )
    monkeypatch.setattr(rag_service, "_vector_store", rag_service.InMemoryVectorStore())

    prompts: list[str] = []
    draft = {
        "originalText": "x",
        "normalizedSentences": [],
        "atomicStorySections": [{"id": "s1", "normalizedSentence": "Original bad content."}],
        "appliedClarificationAnswers": [],
        "unresolvedFields": [],
        "warnings": [],
        "extractionMetadata": {},
    }

    def fake_generate(self: HostedAiClient, request):
        prompts.append(request.prompt)
        content = json.dumps(
            {"facts": [], "sentences": [], "clarificationQuestions": []}
            if request.purpose == "pipeline_clarifications"
            else draft
        )
        return LlmResponse(content=content, response_payload={"content": content}, prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr(HostedAiClient, "generate", fake_generate)

    token = register(client, "hosted-rag@example.com")
    workspace_id, _ = setup_project(client, token)
    raw_text = "A customer can place an order for several products."

    def run_to_final_story(name: str) -> tuple[str, dict]:
        project = client.post(
            f"/api/v1/workspaces/{workspace_id}/projects", headers=auth_header(token), json={"name": name, "description": None}
        )
        assert project.status_code == 201, project.text
        base_url = pipeline_url(workspace_id, project.json()["id"])
        created = client.post(
            base_url, headers=auth_header(token), json={"title": name, "raw_text": raw_text, "generation_mode": "ai"}
        )
        assert created.status_code == 201, created.text
        run = approve_and_proceed(client, token, base_url, created.json())  # -> clarifications
        run = approve_and_proceed(client, token, base_url, run)  # -> final-story
        assert run["current_stage"] == "final-story"
        return base_url, run

    # --- First run: nothing has been corrected yet ---
    base_url, run = run_to_final_story("Hosted RAG A")
    assert prompts and '"pastCorrections"' not in prompts[-1]

    stage = next(item for item in run["stages"] if item["stage_name"] == "final-story")
    corrected = {**draft, "atomicStorySections": [{"id": "s1", "normalizedSentence": "Corrected content."}]}
    saved = client.post(
        f"{base_url}/{run['id']}/stages/final-story/revisions",
        headers=auth_header(token),
        json={"payload": corrected, "expected_version": stage["version_number"]},
    )
    assert saved.status_code == 200, saved.text

    # --- Second run, same input: the fix comes back as context ---
    run_to_final_story("Hosted RAG B")
    assert '"pastCorrections"' in prompts[-1]
    assert "Original bad content." in prompts[-1]
    assert "Corrected content." in prompts[-1]
