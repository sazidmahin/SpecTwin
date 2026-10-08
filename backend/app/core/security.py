import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from uuid import UUID

from app.core.config import settings

_PASSWORD_ITERATIONS = 260000
_ACCESS_TOKEN_PURPOSE = "access"
_PASSWORD_RESET_TOKEN_PURPOSE = "password_reset"


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS
    )
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=_PASSWORD_ITERATIONS,
        salt=_base64url_encode(salt),
        digest=_base64url_encode(digest),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _base64url_decode(salt),
        int(iterations),
    )
    return hmac.compare_digest(_base64url_encode(digest), expected)


def _create_signed_token(
    subject: UUID, *, purpose: str, expires_delta: timedelta
) -> str:
    expires_at = int(time.time() + expires_delta.total_seconds())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(subject), "exp": expires_at, "purpose": purpose}
    signing_input = ".".join(
        [
            _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        settings.secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _decode_signed_token(token: str, *, expected_purpose: str) -> UUID | None:
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}"
        expected_signature = hmac.new(
            settings.secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_base64url_encode(expected_signature), signature):
            return None

        claims = json.loads(_base64url_decode(payload))
        if int(claims.get("exp", 0)) < int(time.time()):
            return None
        if claims.get("purpose", _ACCESS_TOKEN_PURPOSE) != expected_purpose:
            return None
        return UUID(str(claims["sub"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def create_access_token(subject: UUID, expires_delta: timedelta | None = None) -> str:
    return _create_signed_token(
        subject,
        purpose=_ACCESS_TOKEN_PURPOSE,
        expires_delta=expires_delta or timedelta(minutes=settings.access_token_expire_minutes),
    )


def decode_access_token(token: str) -> UUID | None:
    return _decode_signed_token(token, expected_purpose=_ACCESS_TOKEN_PURPOSE)


def create_password_reset_token(subject: UUID) -> str:
    return _create_signed_token(
        subject,
        purpose=_PASSWORD_RESET_TOKEN_PURPOSE,
        expires_delta=timedelta(minutes=settings.password_reset_token_expire_minutes),
    )


def decode_password_reset_token(token: str) -> UUID | None:
    return _decode_signed_token(token, expected_purpose=_PASSWORD_RESET_TOKEN_PURPOSE)
