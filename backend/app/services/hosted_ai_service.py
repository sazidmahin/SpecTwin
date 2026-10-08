"""Platform-managed hosted AI generation ("AI generation" in the UI).

Backed by OpenRouter's OpenAI-compatible chat completions API with a single
server-side key (OPENROUTER_API_KEY), so every user can generate without adding
their own key. Like :class:`OllamaClient` it plugs into the generation pipeline
directly rather than through the BYOK credential system.

The upstream vendor is an implementation detail: the provider is recorded as
"ai" and every message that can reach a user says "AI generation", never the
vendor name.
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.services.llm_service import LlmConfigurationError, LlmExecutionError, LlmRequest, LlmResponse

HOSTED_AI_PROVIDER = "ai"
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class _UpstreamRouteError(Exception):
    """An error body served with HTTP 200, carrying already-scrubbed text."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def hosted_ai_available() -> bool:
    return bool((settings.openrouter_api_key or "").strip() and settings.openrouter_model.strip())


class HostedAiClient:
    provider = HOSTED_AI_PROVIDER

    def __init__(
        self,
        *,
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        timeout_seconds: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.api_key = (api_key or settings.openrouter_api_key or "").strip()
        self.model_name = (model_name or settings.openrouter_model).strip()
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.temperature = settings.openrouter_temperature if temperature is None else temperature
        self.timeout_seconds = timeout_seconds or settings.openrouter_timeout_seconds
        self.max_tokens = max_tokens or settings.openrouter_max_tokens
        # Tried in order when the primary model is rate-limited or down.
        self.fallback_models = [model for model in settings.openrouter_models if model != self.model_name]

    def validate_configuration(self) -> None:
        if not self.api_key or not self.model_name:
            raise LlmConfigurationError("AI generation is not available right now. Please try another engine.")

    # --------------------------------------------------------------- generation
    def generate(self, request: LlmRequest) -> LlmResponse:
        self.validate_configuration()
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": self.temperature,
            "max_tokens": request.max_tokens or self.max_tokens,
        }
        if self.fallback_models:
            body["models"] = [self.model_name, *self.fallback_models]
        if request.response_format == "json" or request.json_schema is not None:
            body["response_format"] = {"type": "json_object"}

        data = self._post_with_retry(body)
        choices = data.get("choices") or []
        if not choices:
            raise LlmExecutionError("AI generation returned an empty answer. Please try again.")
        choice = choices[0] or {}
        message = choice.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise LlmExecutionError("AI generation returned an empty answer. Please try again.")
        # "length" means the answer stopped at the token budget, so JSON output is
        # cut off mid-structure. Say so instead of letting a truncated artifact
        # travel downstream as if the model had answered.
        if choice.get("finish_reason") == "length":
            raise LlmExecutionError(
                "AI generation ran out of room before finishing its answer. "
                "Shorten the requirement text and try again."
            )
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or max(1, len(request.prompt) // 4))
        completion_tokens = int(usage.get("completion_tokens") or max(1, len(content) // 4))
        return LlmResponse(
            content=content,
            response_payload={
                "content": content,
                "provider": self.provider,
                "model_name": str(data.get("model") or self.model_name),
                "done_reason": choice.get("finish_reason"),
            },
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _post_with_retry(self, body: dict[str, Any]) -> dict[str, Any]:
        retries_left = max(0, settings.openrouter_max_retries)
        attempt = 0
        json_mode_dropped = False
        while True:
            try:
                return self._post(body)
            except HTTPError as exc:
                detail = _error_detail(exc)
                # Not every model supports JSON mode. The prompt already asks for
                # JSON, so drop the hint and retry once - but only when the server
                # actually complained about it, so a 400 about the model or the
                # prompt length is not silently turned into a second doomed call.
                if exc.code == 400 and "response_format" in body and not json_mode_dropped and _is_json_mode_error(detail):
                    body = {key: value for key, value in body.items() if key != "response_format"}
                    json_mode_dropped = True
                    continue
                if exc.code in {401, 402, 403}:
                    raise LlmExecutionError("AI generation is not available right now. Please try again later.") from exc
                if exc.code in _RETRYABLE_STATUS and attempt < retries_left:
                    time.sleep(min(2**attempt, 8))
                    attempt += 1
                    continue
                if exc.code == 429:
                    raise LlmExecutionError("AI generation is busy right now. Please try again in a minute.") from exc
                raise LlmExecutionError(f"AI generation failed ({exc.code}): {detail}") from exc
            except _UpstreamRouteError as exc:
                # An error delivered with HTTP 200 (the upstream model failed
                # mid-route) is as transient as a 502, so give it the same budget.
                if attempt < retries_left:
                    time.sleep(min(2**attempt, 8))
                    attempt += 1
                    continue
                raise LlmExecutionError(f"AI generation failed: {exc.detail}") from exc
            except (URLError, OSError, ValueError) as exc:
                if attempt < retries_left:
                    time.sleep(min(2**attempt, 8))
                    attempt += 1
                    continue
                raise LlmExecutionError("AI generation could not be reached. Please try again.") from exc

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Title": settings.project_name,
        }
        if settings.openrouter_site_url:
            headers["HTTP-Referer"] = settings.openrouter_site_url
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed configured endpoint
            data = json.loads(response.read().decode("utf-8"))
        # Errors can also arrive with HTTP 200 (e.g. the upstream model failed mid-route).
        if isinstance(data, dict) and data.get("error"):
            error = data["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise _UpstreamRouteError(_scrub(str(message))[:300])
        return data


def _error_detail(exc: HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", "ignore")
        payload = json.loads(raw)
        error = payload.get("error") if isinstance(payload, dict) else None
        message = error.get("message") if isinstance(error, dict) else raw
    except Exception:  # noqa: BLE001 - best-effort error text
        message = str(exc)
    return _scrub(str(message))[:300]


def _is_json_mode_error(detail: str) -> bool:
    lowered = detail.lower()
    return "response_format" in lowered or "json mode" in lowered or "json_object" in lowered


def _scrub(message: str) -> str:
    """Keep the vendor out of anything a user can see.

    That means the vendor's name, the platform key (upstream errors can quote the
    offending header back) and the model ids, which name the vendor just as
    plainly as "OpenRouter" does - the UI only ever says "AI generation".
    """
    scrubbed = message.replace("OpenRouter", "AI service").replace("openrouter", "ai-service")
    key = (settings.openrouter_api_key or "").strip()
    if key:
        scrubbed = scrubbed.replace(key, "***")
    for model in settings.openrouter_models:
        scrubbed = scrubbed.replace(model, "the AI model")
    return scrubbed
