from datetime import UTC, datetime
import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserAiProviderCredential
from app.services.credential_crypto import decrypt_api_key, encrypt_api_key
from app.services.llm_service import LlmRequest, build_external_llm_client, normalize_external_provider


class AiSettingsError(Exception):
    pass


class AiCredentialNotFoundError(AiSettingsError):
    pass


PROVIDER_LABELS = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Google Gemini"}


def _models(provider: str) -> list[str]:
    models = settings.provider_models(provider)
    if not models:
        raise AiSettingsError(f"No models are configured for {provider}")
    return models


def provider_catalog() -> list[dict[str, Any]]:
    return [
        {
            "provider": provider,
            "label": label,
            "models": _models(provider),
            "default_model": _models(provider)[0],
        }
        for provider, label in PROVIDER_LABELS.items()
    ]


def _safe_credential(credential: UserAiProviderCredential) -> dict[str, Any]:
    return {
        "id": credential.id,
        "provider": credential.provider,
        "configured": True,
        "key_last_four": credential.key_last_four,
        "selected_model": credential.selected_model,
        "is_default": credential.is_default,
        "status": credential.status,
        "validated_at": credential.validated_at,
        "last_used_at": credential.last_used_at,
        "created_at": credential.created_at,
        "updated_at": credential.updated_at,
    }


def list_ai_provider_settings(db: Session, *, user_id: UUID) -> list[dict[str, Any]]:
    credentials = db.scalars(
        select(UserAiProviderCredential).where(UserAiProviderCredential.user_id == user_id)
    ).all()
    by_provider = {item.provider: item for item in credentials}
    response = []
    for catalog in provider_catalog():
        credential = by_provider.get(catalog["provider"])
        response.append(
            {
                **catalog,
                "credential": _safe_credential(credential) if credential else None,
            }
        )
    return response


def list_models_for_credential(db: Session, *, user_id: UUID, provider: str) -> list[str]:
    credential = get_ai_credential(db, user_id=user_id, provider=provider)
    api_key = decrypt_api_key(credential.encrypted_api_key)
    try:
        models = _fetch_provider_models(credential.provider, api_key)
    except (OSError, ValueError, KeyError, URLError) as exc:
        raise AiSettingsError("Unable to load models from this provider") from exc
    if not models:
        raise AiSettingsError("This provider did not return any compatible generation models")
    return models


def _fetch_provider_models(provider: str, api_key: str) -> list[str]:
    if provider == "openai":
        payload = _fetch_json("https://api.openai.com/v1/models", {"Authorization": f"Bearer {api_key}"})
        return sorted({str(item["id"]) for item in payload.get("data", []) if str(item.get("id", "")).startswith(("gpt-", "o"))})
    if provider == "anthropic":
        payload = _fetch_json("https://api.anthropic.com/v1/models?limit=1000", {"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        return sorted({str(item["id"]) for item in payload.get("data", []) if item.get("id")})
    if provider == "gemini":
        payload = _fetch_json(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
        return sorted({str(item["name"]).removeprefix("models/") for item in payload.get("models", []) if "generateContent" in item.get("supportedGenerationMethods", [])})
    raise AiSettingsError("Unsupported AI provider")


def _fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=15) as response:  # noqa: S310 - endpoints are fixed provider APIs
        return json.loads(response.read().decode("utf-8"))


def _validate_model(provider: str, model_name: str) -> str:
    cleaned = model_name.strip()
    if not cleaned:
        raise AiSettingsError("Model name is required")
    if len(cleaned) > 255:
        raise AiSettingsError("Model name is too long")
    return cleaned


def save_ai_credential(
    db: Session,
    *,
    user_id: UUID,
    provider: str,
    api_key: str,
    selected_model: str,
    is_default: bool,
) -> dict[str, Any]:
    normalized = normalize_external_provider(provider)
    if normalized not in PROVIDER_LABELS:
        raise AiSettingsError("Unsupported AI provider")
    cleaned_key = api_key.strip()
    if len(cleaned_key) < 8:
        raise AiSettingsError("API key is too short")
    model = _validate_model(normalized, selected_model)
    existing = db.scalar(
        select(UserAiProviderCredential).where(
            UserAiProviderCredential.user_id == user_id,
            UserAiProviderCredential.provider == normalized,
        )
    )
    has_default = db.scalar(
        select(UserAiProviderCredential.id).where(
            UserAiProviderCredential.user_id == user_id,
            UserAiProviderCredential.is_default.is_(True),
        )
    )
    make_default = is_default or has_default is None
    if make_default:
        db.execute(
            update(UserAiProviderCredential)
            .where(UserAiProviderCredential.user_id == user_id)
            .values(is_default=False)
        )
    if existing is None:
        existing = UserAiProviderCredential(user_id=user_id, provider=normalized)
        db.add(existing)
    existing.encrypted_api_key = encrypt_api_key(cleaned_key)
    existing.key_last_four = cleaned_key[-4:]
    existing.selected_model = model
    existing.is_default = make_default
    existing.status = "configured"
    existing.validated_at = None
    db.commit()
    db.refresh(existing)
    return _safe_credential(existing)


def update_ai_credential(
    db: Session,
    *,
    user_id: UUID,
    provider: str,
    selected_model: str | None,
    is_default: bool | None,
) -> dict[str, Any]:
    credential = get_ai_credential(db, user_id=user_id, provider=provider)
    if selected_model is not None:
        credential.selected_model = _validate_model(credential.provider, selected_model)
        credential.status = "configured"
        credential.validated_at = None
    if is_default is True:
        db.execute(
            update(UserAiProviderCredential)
            .where(UserAiProviderCredential.user_id == user_id)
            .values(is_default=False)
        )
        credential.is_default = True
    elif is_default is False:
        credential.is_default = False
    db.commit()
    db.refresh(credential)
    return _safe_credential(credential)


def get_ai_credential(db: Session, *, user_id: UUID, provider: str) -> UserAiProviderCredential:
    normalized = normalize_external_provider(provider)
    credential = db.scalar(
        select(UserAiProviderCredential).where(
            UserAiProviderCredential.user_id == user_id,
            UserAiProviderCredential.provider == normalized,
        )
    )
    if credential is None:
        raise AiCredentialNotFoundError("AI provider credential is not configured")
    return credential


def get_active_ai_credential(db: Session, *, user_id: UUID) -> UserAiProviderCredential:
    credential = db.scalar(
        select(UserAiProviderCredential).where(
            UserAiProviderCredential.user_id == user_id,
            UserAiProviderCredential.is_default.is_(True),
        )
    )
    if credential is None:
        raise AiCredentialNotFoundError("Configure and activate an AI provider in Settings before using AI-Gen")
    if credential.status != "valid":
        raise AiSettingsError("The active AI provider must pass a connection test before using AI-Gen")
    return credential


def build_client_for_credential(
    credential: UserAiProviderCredential, *, model_name: str | None = None
):
    return build_external_llm_client(
        provider=credential.provider,
        api_key=decrypt_api_key(credential.encrypted_api_key),
        model_name=model_name or credential.selected_model,
    )


def test_ai_credential(db: Session, *, user_id: UUID, provider: str) -> dict[str, Any]:
    credential = get_ai_credential(db, user_id=user_id, provider=provider)
    try:
        response = build_client_for_credential(credential).generate(
            LlmRequest(prompt="Reply with exactly OK.", purpose="credential_test")
        )
    except Exception as exc:
        credential.status = "invalid"
        credential.validated_at = None
        db.commit()
        raise AiSettingsError("Provider connection test failed") from exc
    credential.status = "valid"
    credential.validated_at = datetime.now(UTC)
    db.commit()
    db.refresh(credential)
    return {**_safe_credential(credential), "test_response": response.content[:32]}


def mark_credential_used(db: Session, credential: UserAiProviderCredential) -> None:
    credential.last_used_at = datetime.now(UTC)
    db.commit()


def delete_ai_credential(db: Session, *, user_id: UUID, provider: str) -> None:
    credential = get_ai_credential(db, user_id=user_id, provider=provider)
    was_default = credential.is_default
    db.delete(credential)
    db.flush()
    if was_default:
        replacement = db.scalar(
            select(UserAiProviderCredential)
            .where(UserAiProviderCredential.user_id == user_id)
            .order_by(UserAiProviderCredential.created_at.asc())
        )
        if replacement is not None:
            replacement.is_default = True
    db.commit()
