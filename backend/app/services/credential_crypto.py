import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialCryptoError(Exception):
    pass


def _fernet() -> Fernet:
    secret = settings.ai_credential_encryption_key.strip()
    if not secret:
        raise CredentialCryptoError("AI_CREDENTIAL_ENCRYPTION_KEY is required")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    cleaned = api_key.strip()
    if not cleaned:
        raise CredentialCryptoError("API key is required")
    return "v1:" + _fernet().encrypt(cleaned.encode("utf-8")).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    if not ciphertext.startswith("v1:"):
        raise CredentialCryptoError("Unsupported credential encryption version")
    try:
        return _fernet().decrypt(ciphertext[3:].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise CredentialCryptoError("Stored AI credential could not be decrypted") from exc

