import json
import re
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import LlmCall, PromptTemplate


class LlmServiceError(Exception):
    """Base class for expected LLM service failures."""


class PromptTemplateNotFoundError(LlmServiceError):
    pass


class PromptRenderError(LlmServiceError):
    pass


class LlmExecutionError(LlmServiceError):
    pass


class LlmConfigurationError(LlmServiceError):
    pass


@dataclass(frozen=True)
class LlmRequest:
    prompt: str
    purpose: str
    # Optional hint for providers that can natively constrain generation to valid
    # JSON (e.g. Ollama's "format": "json"). None means the provider's default
    # free-text behavior; providers that don't support this simply ignore it.
    response_format: str | None = None
    # Optional JSON Schema for providers with schema-constrained decoding (Ollama
    # structured outputs). The model can then only emit JSON of exactly this shape.
    json_schema: dict | None = None
    # Optional per-call cap on generated tokens (providers that support it).
    max_tokens: int | None = None


@dataclass(frozen=True)
class LlmResponse:
    content: str
    response_payload: dict
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LlmClient(Protocol):
    provider: str
    model_name: str

    def generate(self, request: LlmRequest) -> LlmResponse:
        """Generate text for the supplied prompt."""


def _json_ready(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text is not None:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        if parts:
            return "".join(parts)
        return json.dumps(_json_ready(content))
    return str(content)


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


class LangChainOpenAIClient:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_name: str,
        temperature: float,
        timeout_seconds: int,
        max_retries: int,
        chat_model: Any | None = None,
    ) -> None:
        cleaned_api_key = api_key.strip() if api_key else ""
        if not cleaned_api_key and chat_model is None:
            raise LlmConfigurationError("An OpenAI API key is required. Add your own key in AI Settings.")

        self.model_name = model_name.strip() or settings.openai_model
        if chat_model is None:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise LlmConfigurationError("langchain-openai is required for OpenAI generation") from exc

            chat_model = ChatOpenAI(
                model=self.model_name,
                api_key=cleaned_api_key,
                temperature=temperature,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        self._chat_model = chat_model

    def generate(self, request: LlmRequest) -> LlmResponse:
        message = self._chat_model.invoke(request.prompt)
        content = _content_to_text(getattr(message, "content", message))
        usage_metadata = getattr(message, "usage_metadata", None) or {}
        if not isinstance(usage_metadata, dict):
            usage_metadata = {}
        response_metadata = getattr(message, "response_metadata", None) or {}
        if not isinstance(response_metadata, dict):
            response_metadata = {}
        token_usage = response_metadata.get("token_usage", {})
        if not isinstance(token_usage, dict):
            token_usage = {}
        prompt_tokens = _first_int(
            usage_metadata.get("input_tokens"),
            token_usage.get("prompt_tokens"),
            token_usage.get("input_tokens"),
            len(request.prompt.split()),
        )
        completion_tokens = _first_int(
            usage_metadata.get("output_tokens"),
            token_usage.get("completion_tokens"),
            token_usage.get("output_tokens"),
            max(1, len(content.split())),
        )
        return LlmResponse(
            content=content,
            response_payload={
                "content": content,
                "provider": self.provider,
                "model_name": self.model_name,
                "usage_metadata": _json_ready(usage_metadata),
                "response_metadata": _json_ready(response_metadata),
            },
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
        )


class _LangChainProviderClient:
    provider = "unknown"

    def __init__(self, *, model_name: str, chat_model: Any) -> None:
        self.model_name = model_name
        self._chat_model = chat_model

    def generate(self, request: LlmRequest) -> LlmResponse:
        message = self._chat_model.invoke(request.prompt)
        content = _content_to_text(getattr(message, "content", message))
        usage_metadata = getattr(message, "usage_metadata", None) or {}
        if not isinstance(usage_metadata, dict):
            usage_metadata = {}
        response_metadata = getattr(message, "response_metadata", None) or {}
        if not isinstance(response_metadata, dict):
            response_metadata = {}
        token_usage = response_metadata.get("token_usage", {})
        if not isinstance(token_usage, dict):
            token_usage = {}
        prompt_tokens = _first_int(
            usage_metadata.get("input_tokens"),
            token_usage.get("prompt_tokens"),
            token_usage.get("input_tokens"),
            len(request.prompt.split()),
        ) or 0
        completion_tokens = _first_int(
            usage_metadata.get("output_tokens"),
            token_usage.get("completion_tokens"),
            token_usage.get("output_tokens"),
            max(1, len(content.split())),
        ) or 0
        return LlmResponse(
            content=content,
            response_payload={
                "content": content,
                "provider": self.provider,
                "model_name": self.model_name,
                "usage_metadata": _json_ready(usage_metadata),
                "response_metadata": _json_ready(response_metadata),
            },
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


class LangChainAnthropicClient(_LangChainProviderClient):
    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_name: str,
        temperature: float,
        timeout_seconds: int,
        max_retries: int,
        chat_model: Any | None = None,
    ) -> None:
        cleaned_api_key = api_key.strip() if api_key else ""
        if not cleaned_api_key and chat_model is None:
            raise LlmConfigurationError("Anthropic API key is required for AI-Gen")
        if chat_model is None:
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError as exc:
                raise LlmConfigurationError("langchain-anthropic is required for Anthropic generation") from exc
            chat_model = ChatAnthropic(
                model=model_name,
                api_key=cleaned_api_key,
                temperature=temperature,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        super().__init__(model_name=model_name, chat_model=chat_model)


class LangChainGeminiClient(_LangChainProviderClient):
    provider = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_name: str,
        temperature: float,
        timeout_seconds: int,
        max_retries: int,
        chat_model: Any | None = None,
    ) -> None:
        cleaned_api_key = api_key.strip() if api_key else ""
        if not cleaned_api_key and chat_model is None:
            raise LlmConfigurationError("Gemini API key is required for AI-Gen")
        if chat_model is None:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError as exc:
                raise LlmConfigurationError("langchain-google-genai is required for Gemini generation") from exc
            chat_model = ChatGoogleGenerativeAI(
                model=model_name,
                api_key=cleaned_api_key,
                temperature=temperature,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        super().__init__(model_name=model_name, chat_model=chat_model)


OPENAI_PROVIDER_NAMES = {"auto", "openai", "langchain-openai", "langchain_openai"}
ANTHROPIC_PROVIDER_NAMES = {"anthropic", "claude", "langchain-anthropic", "langchain_anthropic"}
GEMINI_PROVIDER_NAMES = {"gemini", "google", "google-genai", "langchain-google-genai"}


def normalize_external_provider(provider: str) -> str:
    requested = provider.strip().lower()
    if requested in OPENAI_PROVIDER_NAMES:
        return "openai"
    if requested in ANTHROPIC_PROVIDER_NAMES:
        return "anthropic"
    if requested in GEMINI_PROVIDER_NAMES:
        return "gemini"
    raise LlmConfigurationError(f"Unsupported AI provider: {provider}")


def build_external_llm_client(
    *,
    provider: str,
    api_key: str,
    model_name: str,
    temperature: float = 0,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
) -> LlmClient:
    normalized = normalize_external_provider(provider)
    common = {
        "api_key": api_key,
        "model_name": model_name.strip(),
        "temperature": temperature,
        "timeout_seconds": timeout_seconds if timeout_seconds is not None else settings.openai_timeout_seconds,
        "max_retries": max_retries if max_retries is not None else settings.openai_max_retries,
    }
    if not common["model_name"]:
        raise LlmConfigurationError("Model name is required")
    if normalized == "openai":
        return LangChainOpenAIClient(**common)
    if normalized == "anthropic":
        return LangChainAnthropicClient(**common)
    return LangChainGeminiClient(**common)


def get_or_create_prompt_template(
    db: Session,
    *,
    name: str,
    purpose: str,
    template_text: str,
) -> PromptTemplate:
    template = db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.name == name,
            PromptTemplate.version == 1,
        )
    )
    if template is not None:
        if template.purpose != purpose or template.template_text != template_text or template.status != "active":
            template.purpose = purpose
            template.template_text = template_text
            template.status = "active"
            db.commit()
            db.refresh(template)
        return template

    template = PromptTemplate(
        name=name,
        version=1,
        purpose=purpose,
        template_text=template_text,
        status="active",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_active_prompt_template(db: Session, *, name: str) -> PromptTemplate:
    template = db.scalar(
        select(PromptTemplate)
        .where(PromptTemplate.name == name, PromptTemplate.status == "active")
        .order_by(PromptTemplate.version.desc())
    )
    if template is None:
        raise PromptTemplateNotFoundError("Prompt template not found")
    return template


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render_prompt(template: PromptTemplate, variables: dict[str, str]) -> str:
    """Fill {placeholders} in one pass over the template only.

    Values are never re-scanned, so user text that happens to contain "{name}" is
    inserted verbatim instead of being mistaken for a missing variable.
    """
    missing = [name for name in _PLACEHOLDER.findall(template.template_text) if name not in variables]
    if missing:
        raise PromptRenderError(f"Missing prompt variable: {missing[0]}")
    return _PLACEHOLDER.sub(lambda match: variables[match.group(1)], template.template_text)


def execute_llm_call(
    db: Session,
    *,
    workspace_id: UUID,
    project_id: UUID,
    pipeline_run_id: UUID | None,
    template: PromptTemplate,
    variables: dict[str, str],
    client: LlmClient,
    response_format: str | None = None,
    json_schema: dict | None = None,
    max_tokens: int | None = None,
) -> LlmCall:
    active_client = client
    prompt = render_prompt(template, variables)
    try:
        response = active_client.generate(
            LlmRequest(
                prompt=prompt,
                purpose=template.purpose,
                response_format=response_format,
                json_schema=json_schema,
                max_tokens=max_tokens,
            )
        )
    except Exception as exc:
        provider = getattr(active_client, "provider", "unknown")
        model_name = getattr(active_client, "model_name", "unknown")
        call = LlmCall(
            workspace_id=workspace_id,
            project_id=project_id,
            pipeline_run_id=pipeline_run_id,
            prompt_template_id=template.id,
            provider=provider,
            model_name=model_name,
            status="failed",
            prompt_text=prompt,
            response_payload=None,
            error_message=str(exc),
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        raise LlmExecutionError(str(exc)) from exc

    call = LlmCall(
        workspace_id=workspace_id,
        project_id=project_id,
        pipeline_run_id=pipeline_run_id,
        prompt_template_id=template.id,
        provider=active_client.provider,
        model_name=active_client.model_name,
        status="completed",
        prompt_text=prompt,
        response_payload=response.response_payload,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.total_tokens,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call
