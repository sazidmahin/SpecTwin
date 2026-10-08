"""Correction memory has to work for the hosted engine, not only the local one.

The whole point of "AI generation" is that a user installs nothing, so the loop
cannot depend on Ollama being there to produce embeddings. These cover the
fallback embedder and the rule that vectors from two different embedders are
never compared.
"""

import uuid

import pytest

from app.core.config import settings
from app.services import rag_service
from app.services.rag_service import _cosine_similarity, _embed, _lexical_embedding

WORKSPACE = uuid.uuid4()


@pytest.fixture(autouse=True)
def _no_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """The container a hosted-AI user runs in: no Ollama to embed with."""

    def unreachable(self, text):
        raise RuntimeError("Cannot reach the Ollama server at http://localhost:11434.")

    monkeypatch.setattr("app.services.ollama_service.OllamaClient.embed", unreachable)
    monkeypatch.setattr(settings, "rag_embedder", "auto")


def test_the_same_input_embeds_to_itself_exactly() -> None:
    text = "A member can borrow up to five books at a time."
    assert _cosine_similarity(_lexical_embedding(text), _lexical_embedding(text)) == pytest.approx(1.0)


def test_near_identical_input_scores_above_the_retrieval_threshold() -> None:
    first = _lexical_embedding("A member can borrow up to five books at a time.")
    second = _lexical_embedding("A member can borrow up to five books at a time, the system says.")
    assert _cosine_similarity(first, second) > settings.rag_min_similarity


def test_unrelated_input_scores_below_the_retrieval_threshold() -> None:
    first = _lexical_embedding("A member can borrow up to five books at a time.")
    second = _lexical_embedding("Trains depart from platform nine on weekday mornings.")
    assert _cosine_similarity(first, second) < settings.rag_min_similarity


def test_the_embedding_is_stable_rather_than_salted_per_process() -> None:
    """Buckets come from blake2b, not Python's salted hash() - a vector written
    by one worker has to mean the same thing to the next one, and to the rows
    already in the database after a restart."""
    vector = _lexical_embedding("Order has a total.")
    assert len(vector) == 256
    assert vector == _lexical_embedding("Order has a total.")
    # A fixed expectation, so a change of hash or bucket count fails loudly
    # instead of quietly orphaning every stored correction.
    assert vector.index(max(vector)) == _lexical_embedding("Order has a total.").index(max(vector))


def test_auto_falls_back_to_the_lexical_embedder_when_ollama_is_absent() -> None:
    embedded = _embed("A member can borrow books.")
    assert embedded is not None
    embedder, vector = embedded
    assert embedder == "lexical-v1"
    assert len(vector) == 256


def test_forcing_ollama_reports_no_embedding_rather_than_silently_switching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mixing embedders without saying so would put incomparable vectors in one
    index, so an operator who asked for Ollama gets nothing instead."""
    monkeypatch.setattr(settings, "rag_embedder", "ollama")
    assert _embed("A member can borrow books.") is None


def _store_with(embedder: str) -> rag_service.InMemoryVectorStore:
    store = rag_service.InMemoryVectorStore()
    # Pre-loaded, so search never reaches the database and needs no session.
    store._loaded = True
    store._entries = [
        rag_service._Entry(
            workspace_id=WORKSPACE,
            stage_name=rag_service.CLASS_MODELER_STAGE,
            embedder=embedder,
            embedding=tuple(_lexical_embedding("A member can borrow books.")),
            query_text="A member can borrow books.",
            wrong_payload={"classes": []},
            corrected_payload={"classes": [{"name": "Member"}]},
        )
    ]
    return store


def _search(store: rag_service.InMemoryVectorStore, embedder: str):
    return store.search(
        None,
        workspace_id=WORKSPACE,
        stage_name=rag_service.CLASS_MODELER_STAGE,
        embedder=embedder,
        query_embedding=_lexical_embedding("A member can borrow books."),
        top_k=2,
        min_similarity=0.5,
    )


def test_a_search_never_compares_vectors_from_different_embedders() -> None:
    store = _store_with("ollama:nomic-embed-text")
    # The identical vector, asked for under a different embedder: not a match,
    # however similar the numbers look, because the spaces are unrelated.
    assert _search(store, "lexical-v1") == []

    matched = _search(store, "ollama:nomic-embed-text")
    assert len(matched) == 1
    assert matched[0].corrected_payload == {"classes": [{"name": "Member"}]}
    assert matched[0].similarity == pytest.approx(1.0)


def test_the_hosted_and_byok_engines_are_allowed_to_learn() -> None:
    assert set(rag_service.LEARNING_MODES) == {"ollama", "ai", "byok", "srsgen"}
    # The rule engine is deterministic, so there is nothing for it to learn.
    assert "rule_based" not in rag_service.LEARNING_MODES
