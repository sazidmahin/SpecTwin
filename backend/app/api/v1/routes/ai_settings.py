from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.ai_settings import (
    AiCredentialPatchRequest,
    AiCredentialPutRequest,
    AiCredentialSafeRead,
    AiProviderSettingRead,
)
from app.services.ai_settings_service import (
    AiCredentialNotFoundError,
    AiSettingsError,
    delete_ai_credential,
    list_ai_provider_settings,
    list_models_for_credential,
    save_ai_credential,
    test_ai_credential,
    update_ai_credential,
)
from app.services.hosted_ai_service import hosted_ai_available

router = APIRouter(prefix="/users/me/ai-settings", tags=["ai-settings"])


def _raise_settings_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AiCredentialNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.get("/hosted")
def get_hosted_ai_status(user: User = Depends(get_current_user)) -> dict[str, bool]:
    """Whether the platform's own AI generation (no user key needed) is switched on."""
    del user
    return {"available": hosted_ai_available()}


@router.get("/providers", response_model=list[AiProviderSettingRead])
def get_providers(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return list_ai_provider_settings(db, user_id=user.id)


@router.get("/credentials/{provider}/models", response_model=list[str])
def get_credential_models(
    provider: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    try:
        return list_models_for_credential(db, user_id=user.id, provider=provider)
    except AiSettingsError as exc:
        raise _raise_settings_error(exc) from exc


@router.put("/credentials/{provider}", response_model=AiCredentialSafeRead)
def put_credential(
    provider: str,
    payload: AiCredentialPutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return save_ai_credential(db, user_id=user.id, provider=provider, **payload.model_dump())
    except AiSettingsError as exc:
        raise _raise_settings_error(exc) from exc


@router.patch("/credentials/{provider}", response_model=AiCredentialSafeRead)
def patch_credential(
    provider: str,
    payload: AiCredentialPatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return update_ai_credential(db, user_id=user.id, provider=provider, **payload.model_dump())
    except AiSettingsError as exc:
        raise _raise_settings_error(exc) from exc


@router.post("/credentials/{provider}/test", response_model=AiCredentialSafeRead)
def test_credential(
    provider: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return test_ai_credential(db, user_id=user.id, provider=provider)
    except AiSettingsError as exc:
        raise _raise_settings_error(exc) from exc


@router.delete("/credentials/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def remove_credential(
    provider: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_ai_credential(db, user_id=user.id, provider=provider)
    except AiSettingsError as exc:
        raise _raise_settings_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
