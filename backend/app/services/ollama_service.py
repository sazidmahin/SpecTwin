"""Local AI generation backed by an Ollama server.

Ollama is a platform-managed local provider (no per-user API key), so it plugs
into the generation pipeline the same way :class:`SrsGenClient` does rather than
through the BYOK credential system.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.services.llm_service import LlmConfigurationError, LlmExecutionError, LlmRequest, LlmResponse


def _base_url() -> str:
    return settings.ollama_base_url.rstrip("/")


class OllamaRepeatLoopAborted(LlmExecutionError):
    """Ollama's own hard circuit breaker (separate from our repeat_penalty
    tuning - see Settings.ollama_repeat_penalty) aborted generation outright
    because the model got stuck repeating itself. A distinct type so
    OllamaClient.generate() can retry automatically (see _MAX_REPEAT_ABORT_RETRIES)
    instead of making the caller click regenerate by hand - with temperature > 0
    this is usually a one-attempt-unlucky failure, not a deterministic dead end."""


def _raise_ollama_failure(detail: str, *, cause: BaseException | None = None) -> None:
    """Raise with a message that explains what a bare engine string like
    "prediction aborted, token repeat limit reached" actually means, instead of
    surfacing it as-is."""
    if "token repeat limit" in detail.lower() or "prediction aborted" in detail.lower():
        raise OllamaRepeatLoopAborted(
            "Ollama aborted this generation because the model got stuck repeating itself "
            "(its own token-repeat safety limit, not a bug in the request). Try regenerating "
            "this stage - it often succeeds on a retry - or switch to a larger model "
            "(e.g. qwen2.5) if this keeps happening on this task."
        ) from cause
    raise LlmExecutionError(f"Ollama generation failed: {detail}") from cause


class OllamaClient:
    provider = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        timeout_seconds: int | None = None,
        keep_alive: str | None = None,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        repeat_penalty: float | None = None,
        repeat_last_n: int | None = None,
    ) -> None:
        self.base_url = (base_url or _base_url()).rstrip("/")
        self.model_name = (model_name or settings.ollama_model).strip()
        self.temperature = settings.ollama_temperature if temperature is None else temperature
        self.timeout_seconds = timeout_seconds or settings.ollama_timeout_seconds
        self.keep_alive = keep_alive or settings.ollama_keep_alive
        self.num_ctx = num_ctx or settings.ollama_num_ctx
        # Cap output length: without this, a small local model asked to do a task
        # beyond its ability can ramble/repeat indefinitely instead of naturally
        # stopping, turning a call that should take seconds into one that takes
        # minutes and often still fails to produce usable JSON.
        self.num_predict = num_predict or settings.ollama_num_predict
        # See Settings.ollama_repeat_penalty - counters greedy-decoding repetition
        # loops (a stuck model re-emitting the same tokens until num_predict cuts
        # it off) without touching temperature/determinism otherwise.
        self.repeat_penalty = settings.ollama_repeat_penalty if repeat_penalty is None else repeat_penalty
        self.repeat_last_n = settings.ollama_repeat_last_n if repeat_last_n is None else repeat_last_n
        if not self.model_name:
            raise LlmConfigurationError("OLLAMA_MODEL is required for local Ollama generation")

    # ------------------------------------------------------------------ helpers
    def _get(self, path: str) -> dict[str, Any]:
        request = Request(f"{self.base_url}{path}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed local endpoint
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def available_models(self) -> list[str]:
        try:
            payload = self._get("/api/tags")
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise LlmConfigurationError(
                f"Cannot reach the Ollama server at {self.base_url}. Is the 'ollama' service running?"
            ) from exc
        models = payload.get("models") or []
        names: list[str] = []
        for item in models:
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
                names.append(name.split(":", 1)[0])
        return list(dict.fromkeys(names))

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        """Embed a short piece of text via Ollama's embedding endpoint.

        Used only by the RAG correction-memory feature (rag_service.py), gated by
        RAG_ENABLED - embedding calls are cheap (a single forward pass, not
        autoregressive generation) so this stays fast even on CPU, but it is still
        a network round trip, so callers should skip it entirely when RAG is off.
        """
        embed_model = (model or settings.ollama_embed_model).strip()
        try:
            data = self._post("/api/embeddings", {"model": embed_model, "prompt": text})
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else str(exc)
            raise LlmExecutionError(f"Ollama embedding failed ({exc.code}): {detail}") from exc
        except (URLError, OSError, ValueError) as exc:
            raise LlmExecutionError(f"Ollama embedding failed: {exc}") from exc
        embedding = data.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise LlmExecutionError("Ollama embedding response had no embedding vector")
        return [float(value) for value in embedding]

    def validate_configuration(self) -> None:
        available = self.available_models()
        wanted = self.model_name
        if wanted in available or wanted.split(":", 1)[0] in available:
            return
        raise LlmConfigurationError(
            f"Ollama model '{wanted}' is not installed on {self.base_url}. "
            f"Run: ollama pull {wanted}"
        )

    # --------------------------------------------------------------- budgets
    def input_token_budget(self, num_predict: int | None = None, *, overhead_tokens: int = 700) -> int:
        """Tokens of task input (user text, story, requirements) one call can carry.

        The window is fixed (see Settings.ollama_num_ctx), so the room left for input
        is what remains after the completion budget and the fixed prompt scaffolding.
        Capped by ollama_chunk_tokens: small models answer shorter prompts better.
        """
        completion = num_predict or self.num_predict
        room = self.num_ctx - completion - overhead_tokens
        return max(400, min(room, settings.ollama_chunk_tokens))

    def warm_up(self) -> None:
        """Load the model with the same options real calls use, so the first stage
        does not pay the model-load time. Best effort: failures are ignored."""
        try:
            self._post(
                "/api/chat",
                {
                    "model": self.model_name,
                    "messages": [],
                    "keep_alive": self.keep_alive,
                    "options": self._options(1),
                },
            )
        except Exception:  # noqa: BLE001 - warm-up must never break a request
            pass

    # --------------------------------------------------------------- generation
    # Temperature > 0 (see Settings.ollama_temperature) means a repeat-loop abort
    # is usually one unlucky sampling path, not a deterministic dead end - a
    # couple of automatic retries turn most of these into a successful call
    # instead of pushing the user to click regenerate by hand each time.
    _MAX_REPEAT_ABORT_RETRIES = 2

    def generate(self, request: LlmRequest) -> LlmResponse:
        attempt = 0
        while True:
            try:
                return self._generate_once(request)
            except OllamaRepeatLoopAborted:
                if attempt >= self._MAX_REPEAT_ABORT_RETRIES:
                    raise
                attempt += 1

    def _options(self, num_predict: int) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": self.temperature,
            # Always the same window: changing num_ctx between calls makes Ollama
            # reload the model, which on a CPU laptop costs seconds every time.
            "num_ctx": self.num_ctx,
            "num_predict": num_predict,
            "repeat_penalty": self.repeat_penalty,
            "repeat_last_n": self.repeat_last_n,
        }
        if settings.ollama_num_thread:
            options["num_thread"] = settings.ollama_num_thread
        return options

    def _generate_once(self, request: LlmRequest) -> LlmResponse:
        num_predict = request.max_tokens or self.num_predict
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": self._options(num_predict),
        }
        if request.json_schema is not None:
            # Structured outputs: Ollama compiles the schema into a grammar, so every
            # sampled token keeps the answer valid JSON of exactly this shape.
            body["format"] = request.json_schema
        elif request.response_format == "json":
            body["format"] = "json"
        try:
            data = self._post("/api/chat", body)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else str(exc)
            _raise_ollama_failure(detail, cause=exc)
        except (URLError, OSError, ValueError) as exc:
            raise LlmExecutionError(
                f"Ollama generation failed ({exc}). Is Ollama running at {self.base_url}?"
            ) from exc
        if data.get("error"):
            _raise_ollama_failure(str(data["error"]))

        message = data.get("message") or {}
        content = str(message.get("content") or data.get("response") or "").strip()
        prompt_tokens = int(data.get("prompt_eval_count") or max(1, len(request.prompt) // 4))
        completion_tokens = int(data.get("eval_count") or max(1, len(content) // 4))
        done_reason = data.get("done_reason")
        if done_reason is None and completion_tokens >= num_predict:
            done_reason = "length"
        return LlmResponse(
            content=content,
            response_payload={
                "content": content,
                "provider": self.provider,
                "model_name": self.model_name,
                "done_reason": done_reason,
                "num_ctx": self.num_ctx,
                "num_predict": num_predict,
                # Nanosecond timings from Ollama, kept for diagnosing slow stages.
                "load_duration": data.get("load_duration"),
                "prompt_eval_duration": data.get("prompt_eval_duration"),
                "eval_duration": data.get("eval_duration"),
                "total_duration": data.get("total_duration"),
            },
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def ollama_models() -> list[str]:
    """Configured model catalogue for the Ollama provider."""
    return settings.provider_models("ollama") or [settings.ollama_model]
