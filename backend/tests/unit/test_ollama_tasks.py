from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.services.llm_json import parse_json_response
from app.services.llm_service import LlmRequest, LlmResponse, get_or_create_prompt_template, render_prompt
from app.services.ollama_service import OllamaClient
from app.services.ollama_tasks import (
    CHARS_PER_TOKEN,
    CallContext,
    OutputTruncated,
    halve_text,
    json_task,
    map_chunks,
    pack_items,
    split_text,
)

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "string"}}},
    "required": ["items"],
}


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class ScriptedOllama(OllamaClient):
    """Returns queued answers; a (text, cut_off) tuple simulates hitting num_predict."""

    def __init__(self, answers: list) -> None:
        super().__init__(model_name="llama3.2:1b")
        self.answers = list(answers)
        self.requests: list[LlmRequest] = []

    def generate(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        answer = self.answers.pop(0)
        content, cut_off = answer if isinstance(answer, tuple) else (answer, False)
        payload = {"content": content, "done_reason": "length" if cut_off else "stop"}
        return LlmResponse(content=content, response_payload=payload, prompt_tokens=10, completion_tokens=5)


def _ctx(db: Session) -> CallContext:
    return CallContext(db=db, workspace_id=uuid4(), project_id=uuid4(), pipeline_run_id=None)


def _task(db: Session, client: OllamaClient, data: dict):
    return json_task(
        _ctx(db),
        client,
        name="test_task",
        purpose="test_task",
        instruction="List the items.",
        schema=SCHEMA,
        example='{"items": ["a"]}',
        data=data,
        num_predict=256,
    )


def test_split_text_keeps_every_word_in_order_and_respects_the_budget() -> None:
    text = "\n\n".join(f"Paragraph {p}. " + " ".join(f"Sentence {p}-{s} has words." for s in range(40)) for p in range(6))
    chunks = split_text(text, max_tokens=200)
    assert len(chunks) > 1
    assert all(len(chunk) <= 200 * CHARS_PER_TOKEN for chunk in chunks)
    assert " ".join(chunks).split() == text.split()
    assert split_text("short text", 200) == ["short text"]


def test_pack_items_and_halving() -> None:
    items = [f"The system shall do thing number {i}." for i in range(50)]
    batches = pack_items(items, max_tokens=60)
    assert len(batches) > 1 and [item for batch in batches for item in batch] == items
    halves = halve_text(" ".join(items))
    assert len(halves) == 2 and " ".join(halves).split() == " ".join(items).split()


def test_parse_json_response_repairs_cut_off_and_wrapped_answers() -> None:
    assert parse_json_response('{"classes": [{"name": "A"}, {"name": "B", "fie') == {"classes": [{"name": "A"}]}
    assert parse_json_response('Sure! Here it is:\n```json\n{"items": ["x", "y",]}\n```') == {"items": ["x", "y"]}
    assert parse_json_response("no json at all") is None


def test_render_prompt_leaves_braces_in_user_text_alone(db_session: Session) -> None:
    template = get_or_create_prompt_template(db_session, name="t", purpose="t", template_text="Data: {data} / {example}")
    rendered = render_prompt(template, {"data": 'User wrote {"x": 1} and {placeholder}', "example": "{}"})
    assert rendered == 'Data: User wrote {"x": 1} and {placeholder} / {}'


def test_json_task_sends_schema_and_budget(db_session: Session) -> None:
    client = ScriptedOllama(['{"items": ["a", "b"]}'])
    result = _task(db_session, client, {"text": "a and b"})
    assert result.payload == {"items": ["a", "b"]} and not result.reformatted
    request = client.requests[0]
    assert request.json_schema == SCHEMA and request.max_tokens == 256
    assert '{"text":"a and b"}' in request.prompt


def test_json_task_asks_the_model_to_reformat_a_prose_answer(db_session: Session) -> None:
    client = ScriptedOllama(["The items are:\n- a\n- b", '{"items": ["a", "b"]}'])
    result = _task(db_session, client, {"text": "a and b"})
    assert result.payload == {"items": ["a", "b"]} and result.reformatted
    assert client.requests[1].purpose == "ollama_json_reformat"
    assert "- a" in client.requests[1].prompt


def test_json_task_returns_raw_text_when_even_the_reformat_fails(db_session: Session) -> None:
    client = ScriptedOllama(["just prose", "still prose"])
    result = _task(db_session, client, {"text": "x"})
    assert result.payload is None and result.raw_text == "just prose"


def test_cut_off_answer_is_split_and_retried(db_session: Session) -> None:
    client = ScriptedOllama([('{"items": ["a", "b', True), '{"items": ["a"]}', '{"items": ["b"]}'])
    # Cut off and unrecoverable -> OutputTruncated; cut off but repairable -> flagged.
    with pytest.raises(OutputTruncated):
        _task(db_session, ScriptedOllama([('Sure, the items are', True)]), {"text": "x"})
    assert _task(db_session, ScriptedOllama([('{"items": ["a", "b', True)]), {"text": "x"}).truncated
    text = "First half sentence here. " * 20 + "Second half sentence here. " * 20
    results = map_chunks([text], lambda chunk: _task(db_session, client, {"text": chunk}), halve_text)
    assert [result.payload for result in results] == [{"items": ["a"]}, {"items": ["b"]}]
    assert len(client.requests) == 3

    # A chunk that cannot be split any further keeps its repaired partial answer.
    partial = ScriptedOllama([('{"items": ["a", "b', True)])
    results = map_chunks(["x"], lambda chunk: _task(db_session, partial, {"text": chunk}), lambda chunk: [chunk])
    assert results[0].payload == {"items": ["a", "b"]}


def test_ollama_client_uses_a_fixed_window_and_schema_format(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    def fake_post(self, path, payload):
        sent.append(payload)
        return {"message": {"content": '{"items": []}'}, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 3}

    monkeypatch.setattr(OllamaClient, "_post", fake_post)
    client = OllamaClient(model_name="llama3.2:1b")
    short = LlmRequest(prompt="x", purpose="p", json_schema=SCHEMA, max_tokens=128)
    long = LlmRequest(prompt="y " * 5000, purpose="p", response_format="json")
    client.generate(short)
    client.generate(long)
    assert sent[0]["options"]["num_ctx"] == sent[1]["options"]["num_ctx"] == settings.ollama_num_ctx
    assert sent[0]["format"] == SCHEMA and sent[1]["format"] == "json"
    assert sent[0]["options"]["num_predict"] == 128
    assert sent[0]["keep_alive"] == settings.ollama_keep_alive
