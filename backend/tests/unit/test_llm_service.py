import sys
from collections.abc import Generator
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.services.llm_service import (
    LangChainAnthropicClient,
    LangChainGeminiClient,
    LangChainOpenAIClient,
    LlmConfigurationError,
    LlmExecutionError,
    LlmRequest,
    build_external_llm_client,
    execute_llm_call,
    get_or_create_prompt_template,
    render_prompt,
)
from tests.unit.fake_llm import FakeStructuredLlmClient


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


class FailingClient:
    provider = "openai"
    model_name = "failing-model"

    def generate(self, request: LlmRequest):
        raise RuntimeError("provider unavailable")


def test_openai_client_requires_user_api_key() -> None:
    with pytest.raises(LlmConfigurationError, match="AI Settings"):
        LangChainOpenAIClient(api_key=None, model_name="gpt-test", temperature=0, timeout_seconds=30, max_retries=0)


def test_langchain_openai_client_invokes_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    fake_module = ModuleType("langchain_openai")

    class FakeMessage:
        content = [{"type": "text", "text": "generated content"}]
        usage_metadata = {"input_tokens": 3, "output_tokens": 5}
        response_metadata = {"token_usage": {"total_tokens": 8}}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["kwargs"] = kwargs

        def invoke(self, prompt: str) -> FakeMessage:
            captured["prompt"] = prompt
            return FakeMessage()

    fake_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)

    client = LangChainOpenAIClient(
        api_key="sk-test",
        model_name="gpt-test",
        temperature=0,
        timeout_seconds=30,
        max_retries=2,
    )
    response = client.generate(LlmRequest(prompt="Summarize claims", purpose="summary"))

    assert captured["kwargs"] == {
        "model": "gpt-test",
        "api_key": "sk-test",
        "temperature": 0,
        "timeout": 30,
        "max_retries": 2,
    }
    assert captured["prompt"] == "Summarize claims"
    assert response.content == "generated content"
    assert response.prompt_tokens == 3
    assert response.completion_tokens == 5
    assert response.total_tokens == 8
    assert response.response_payload["provider"] == "openai"
    assert response.response_payload["model_name"] == "gpt-test"


@pytest.mark.parametrize(
    ("provider", "module_name", "class_name", "expected_type"),
    [
        ("anthropic", "langchain_anthropic", "ChatAnthropic", LangChainAnthropicClient),
        ("gemini", "langchain_google_genai", "ChatGoogleGenerativeAI", LangChainGeminiClient),
    ],
)
def test_external_provider_clients_use_selected_model(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    module_name: str,
    class_name: str,
    expected_type: type,
) -> None:
    captured: dict[str, object] = {}
    fake_module = ModuleType(module_name)

    class FakeChatModel:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    setattr(fake_module, class_name, FakeChatModel)
    monkeypatch.setitem(sys.modules, module_name, fake_module)

    client = build_external_llm_client(
        provider=provider,
        api_key="provider-key",
        model_name="selected-model",
        temperature=0,
        timeout_seconds=15,
        max_retries=1,
    )

    assert isinstance(client, expected_type)
    assert client.model_name == "selected-model"
    assert captured == {
        "model": "selected-model",
        "api_key": "provider-key",
        "temperature": 0,
        "timeout": 15,
        "max_retries": 1,
    }


def test_prompt_template_is_versioned_and_renders_variables(db_session: Session) -> None:
    template = get_or_create_prompt_template(
        db_session,
        name="summary_sections",
        purpose="summary",
        template_text="Summarize {raw_text}",
    )
    same_template = get_or_create_prompt_template(
        db_session,
        name="summary_sections",
        purpose="summary",
        template_text="Ignored update {raw_text}",
    )

    assert same_template.id == template.id
    assert template.version == 1
    assert render_prompt(template, {"raw_text": "claims workflow"}) == "Ignored update claims workflow"


def test_execute_llm_call_logs_completed_call(db_session: Session) -> None:
    template = get_or_create_prompt_template(
        db_session,
        name="summary_sections",
        purpose="summary",
        template_text="Summarize {raw_text}",
    )

    call = execute_llm_call(
        db_session,
        workspace_id=uuid4(),
        project_id=uuid4(),
        pipeline_run_id=None,
        template=template,
        variables={"raw_text": "users submit claims"},
        client=FakeStructuredLlmClient(),
    )

    assert call.status == "completed"
    assert call.provider == "openai"
    assert call.model_name == "fake-openai-test-model"
    assert call.prompt_tokens > 0
    assert call.total_tokens == call.prompt_tokens + call.completion_tokens
    assert call.response_payload is not None
    assert "Summary generated" in call.response_payload["content"]


def test_execute_llm_call_logs_failed_call(db_session: Session) -> None:
    template = get_or_create_prompt_template(
        db_session,
        name="summary_sections",
        purpose="summary",
        template_text="Summarize {raw_text}",
    )

    with pytest.raises(LlmExecutionError):
        execute_llm_call(
            db_session,
            workspace_id=uuid4(),
            project_id=uuid4(),
            pipeline_run_id=None,
            template=template,
            variables={"raw_text": "users submit claims"},
            client=FailingClient(),
        )
