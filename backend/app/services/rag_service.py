"""Correction-memory RAG loop for every AI engine.

Whenever a user edits something an AI engine produced - a pipeline stage before
approving it, or a class model in the Class Modeler - that edit is captured as a
(wrong, corrected) pair. On future generations the most similar past corrections
are looked up and fed into the prompt as "you got this wrong before, here is
what was actually correct" examples, so the same input stops producing the same
mistake.

Two things make this work for every engine rather than only the local one:

- Scope. Any model-authored mode (ollama, ai, byok, srsgen) captures and
  retrieves. Only the rule engine is excluded, because it is deterministic and
  has nothing to learn.
- Embeddings. Ollama's embedding endpoint is used when it is actually there, but
  the whole point of the hosted "AI generation" engine is that a user needs no
  local setup, so there is a built-in lexical embedder as a fallback that needs
  no service at all. Vectors from the two live in different spaces, so every row
  records which embedder wrote it and a search only compares rows that match.

Entirely gated by settings.rag_enabled - when off, no embedding work is done,
nothing is captured, and generation behaves exactly as it did before this
feature existed. Corrections are persisted to the generation_corrections table
so they survive a restart; similarity search itself runs over an in-memory
index built from that table, avoiding a pgvector/external vector-DB dependency
for what is expected to stay a small number of rows.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import GenerationCorrection, GenerationPipelineRun
from app.services.ollama_service import OllamaClient

logger = logging.getLogger(__name__)

# Modes whose output a model wrote, and can therefore get wrong in a way worth
# remembering. "rule_based" is deterministic, so it never learns anything.
LEARNING_MODES = frozenset({"ollama", "ai", "byok", "srsgen"})
# Stages the rule engine always produces, whatever the run's mode.
_RULE_ENGINE_STAGES = frozenset({"input", "xml"})

_LEXICAL_DIMENSIONS = 256
_LEXICAL_EMBEDDER = "lexical-v1"
_TOKENS = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class CorrectionMatch:
    query_text: str
    wrong_payload: dict[str, Any]
    corrected_payload: dict[str, Any]
    similarity: float


@dataclass(frozen=True)
class _Entry:
    """A stored correction, detached from the ORM.

    The index outlives the session a row was read in, so it keeps plain values;
    holding the ORM object would expire its attributes on the next commit and
    re-query a session that may already be closed.
    """

    workspace_id: UUID
    stage_name: str
    embedder: str
    embedding: tuple[float, ...]
    query_text: str
    wrong_payload: dict[str, Any]
    corrected_payload: dict[str, Any]


def _cosine_similarity(a: tuple[float, ...] | list[float], b: tuple[float, ...] | list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _lexical_embedding(text: str) -> list[float]:
    """A hashed bag of word unigrams and bigrams, L2-normalised.

    Cosine over this is a lexical overlap score: the same requirement text
    scores 1.0 against itself and near-identical text scores close to it, which
    is exactly the "this input again" case correction memory is for. It needs no
    model, no network and no extra dependency, and blake2b keeps the buckets
    stable across processes in a way Python's salted hash() would not.
    """
    tokens = _TOKENS.findall(text.lower())
    grams = [*tokens, *(f"{first} {second}" for first, second in zip(tokens, tokens[1:]))]
    vector = [0.0] * _LEXICAL_DIMENSIONS
    for gram in grams:
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % _LEXICAL_DIMENSIONS
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _embed(text: str) -> tuple[str, list[float]] | None:
    """The embedder to use and the vector it produced, or None if neither works.

    "ollama" and "lexical" force one; "auto" prefers Ollama when it answers and
    silently drops to the lexical embedder when it does not, so a user running
    the hosted engine with no local model still gets correction memory.
    """
    choice = (settings.rag_embedder or "auto").strip().lower()
    if choice != "lexical":
        try:
            client = OllamaClient()
            return f"ollama:{settings.ollama_embed_model}", client.embed(text)
        except Exception as exc:  # noqa: BLE001 - RAG must never break generation
            if choice == "ollama":
                logger.warning("RAG embedding call failed and no fallback is allowed, skipping: reason=%s", exc)
                return None
            logger.info("RAG embedding fell back to the lexical embedder: reason=%s", exc)
    return _LEXICAL_EMBEDDER, _lexical_embedding(text)


class InMemoryVectorStore:
    """A small in-process index of stored corrections.

    Rebuilt from the database lazily on first use per worker process. This is
    intentionally not a persistent store itself - generation_corrections rows in
    Postgres are the durable record; this is just a fast runtime cache over them.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._entries: list[_Entry] = []

    def _ensure_loaded(self, db: Session) -> None:
        if self._loaded:
            return
        self._entries = [_entry_of(row) for row in db.scalars(select(GenerationCorrection)).all()]
        self._loaded = True

    def add(self, row: GenerationCorrection) -> None:
        self._entries.append(_entry_of(row))

    def reset(self) -> None:
        """Drop the cache so the next search reloads from the database."""
        self._loaded = False
        self._entries = []

    def search(
        self,
        db: Session,
        *,
        workspace_id: UUID,
        stage_name: str,
        embedder: str,
        query_embedding: list[float],
        top_k: int,
        min_similarity: float,
    ) -> list[CorrectionMatch]:
        self._ensure_loaded(db)
        scored: list[tuple[float, _Entry]] = []
        for entry in self._entries:
            if entry.workspace_id != workspace_id or entry.stage_name != stage_name:
                continue
            # Comparing across embedders is meaningless, not merely inaccurate.
            if entry.embedder != embedder:
                continue
            similarity = _cosine_similarity(query_embedding, entry.embedding)
            if similarity >= min_similarity:
                scored.append((similarity, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            CorrectionMatch(
                query_text=entry.query_text,
                wrong_payload=entry.wrong_payload,
                corrected_payload=entry.corrected_payload,
                similarity=similarity,
            )
            for similarity, entry in scored[:top_k]
        ]


def _entry_of(row: GenerationCorrection) -> _Entry:
    return _Entry(
        workspace_id=row.workspace_id,
        stage_name=row.stage_name,
        embedder=row.embedding_model or f"ollama:{settings.ollama_embed_model}",
        embedding=tuple(row.embedding or ()),
        query_text=row.query_text,
        wrong_payload=row.wrong_payload,
        corrected_payload=row.corrected_payload,
    )


_vector_store = InMemoryVectorStore()


def _store(
    db: Session,
    *,
    workspace_id: UUID,
    project_id: UUID,
    run_id: UUID | None,
    stage_name: str,
    generation_mode: str,
    query_text: str,
    wrong_payload: dict[str, Any],
    corrected_payload: dict[str, Any],
) -> bool:
    if not settings.rag_enabled or generation_mode not in LEARNING_MODES:
        return False
    if wrong_payload == corrected_payload:
        return False
    embedded = _embed(query_text)
    if embedded is None:
        return False
    embedder, embedding = embedded
    row = GenerationCorrection(
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        stage_name=stage_name,
        generation_mode=generation_mode,
        query_text=query_text,
        embedding=embedding,
        embedding_model=embedder,
        wrong_payload=wrong_payload,
        corrected_payload=corrected_payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _vector_store.add(row)
    return True


def _search(
    db: Session, *, workspace_id: UUID, stage_name: str, generation_mode: str, query_text: str
) -> list[CorrectionMatch]:
    if not settings.rag_enabled or generation_mode not in LEARNING_MODES:
        return []
    embedded = _embed(query_text)
    if embedded is None:
        return []
    embedder, embedding = embedded
    return _vector_store.search(
        db,
        workspace_id=workspace_id,
        stage_name=stage_name,
        embedder=embedder,
        query_embedding=embedding,
        top_k=settings.rag_top_k,
        min_similarity=settings.rag_min_similarity,
    )


def capture_correction(
    db: Session,
    *,
    run: GenerationPipelineRun,
    stage_name: str,
    wrong_payload: dict[str, Any],
    corrected_payload: dict[str, Any],
) -> None:
    """Record that a user corrected an AI-authored pipeline stage draft."""
    if stage_name in _RULE_ENGINE_STAGES:
        return  # always rule-engine output, never model-authored, whatever the mode
    _store(
        db,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        run_id=run.id,
        stage_name=stage_name,
        generation_mode=run.generation_mode,
        query_text=run.raw_text,
        wrong_payload=wrong_payload,
        corrected_payload=corrected_payload,
    )


def retrieve_corrections(db: Session, *, run: GenerationPipelineRun, stage_name: str) -> list[CorrectionMatch]:
    if stage_name in _RULE_ENGINE_STAGES:
        return []
    return _search(
        db,
        workspace_id=run.workspace_id,
        stage_name=stage_name,
        generation_mode=run.generation_mode,
        query_text=run.raw_text,
    )


# The Class Modeler keeps no run, so its memories get their own stage name - its
# model has a different shape from the pipeline's class-model stage payload and
# the two must never be offered to each other as examples.
CLASS_MODELER_STAGE = "class-modeler"


def capture_model_correction(
    db: Session,
    *,
    workspace_id: UUID,
    project_id: UUID,
    generation_mode: str,
    requirement_text: str,
    wrong_model: dict[str, Any],
    corrected_model: dict[str, Any],
) -> bool:
    """Record that a user fixed a class model the LLM or AI engine generated.

    Returns whether anything was stored, so the caller can tell the user plainly
    whether the fix will be remembered rather than implying it always is.
    """
    return _store(
        db,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=None,
        stage_name=CLASS_MODELER_STAGE,
        generation_mode=generation_mode,
        query_text=requirement_text,
        wrong_payload=wrong_model,
        corrected_payload=corrected_model,
    )


def retrieve_model_corrections(
    db: Session, *, workspace_id: UUID, generation_mode: str, requirement_text: str
) -> list[CorrectionMatch]:
    return _search(
        db,
        workspace_id=workspace_id,
        stage_name=CLASS_MODELER_STAGE,
        generation_mode=generation_mode,
        query_text=requirement_text,
    )


def format_corrections_for_prompt(matches: list[CorrectionMatch]) -> list[dict[str, Any]]:
    """Shape corrections for inclusion in the generic upstream JSON blob, so the
    model sees them the same way it sees rawText/previousArtifact/clarificationContext.
    """
    return [
        {
            "similarPastInput": match.query_text,
            "youIncorrectlyProduced": match.wrong_payload,
            "theCorrectAnswerWas": match.corrected_payload,
        }
        for match in matches
    ]
