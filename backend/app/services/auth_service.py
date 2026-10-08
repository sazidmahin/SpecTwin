import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.db.models import User, Workspace, WorkspaceMember
from app.services.email_service import send_verification_code

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_VERIFICATION_ATTEMPTS = 5


class AuthError(Exception):
    """Base class for expected authentication failures."""


class DuplicateEmailError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class EmailVerificationRequiredError(AuthError):
    pass


class InvalidRegistrationError(AuthError):
    pass


class InvalidPasswordResetTokenError(AuthError):
    pass


class InvalidEmailVerificationCodeError(AuthError):
    pass


class VerificationResendCooldownError(AuthError):
    pass


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    user: User


@dataclass(frozen=True)
class RegistrationResult:
    verification_code: str | None


@dataclass(frozen=True)
class PasswordResetRequestResult:
    reset_token: str | None


@dataclass(frozen=True)
class VerificationCodeResult:
    verification_code: str | None


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise InvalidRegistrationError("Invalid email address")
    return normalized


def _workspace_slug(full_name: str, user_id: UUID) -> str:
    base = _SLUG_RE.sub("-", full_name.strip().lower()).strip("-") or "personal"
    return f"{base}-{str(user_id)[:8]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _set_verification_code(user: User) -> str:
    code = _generate_verification_code()
    sent_at = _now()
    user.email_verification_code_hash = hash_password(code)
    user.email_verification_expires_at = sent_at + timedelta(
        minutes=settings.email_verification_code_expire_minutes
    )
    user.email_verification_attempts = 0
    user.email_verification_sent_at = sent_at
    return code


def _local_verification_code(code: str) -> str | None:
    if settings.email_delivery_mode == "console":
        return code
    return None


def register_user(db: Session, *, email: str, password: str, full_name: str) -> RegistrationResult:
    normalized_email = _normalize_email(email)
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise DuplicateEmailError("Email is already registered")

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        status="inactive",
        email_verified=False,
        email_verified_at=None,
    )
    db.add(user)
    db.flush()

    workspace = Workspace(
        name=f"{user.full_name}'s Workspace",
        slug=_workspace_slug(user.full_name, user.id),
        type="personal",
        owner_user_id=user.id,
        status="active",
    )
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="active",
    )
    db.add(membership)

    code = _set_verification_code(user)
    send_verification_code(email=user.email, code=code, full_name=user.full_name)
    db.commit()

    return RegistrationResult(verification_code=_local_verification_code(code))


def verify_email(db: Session, *, email: str, code: str) -> AuthResult:
    normalized_email = _normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise InvalidEmailVerificationCodeError("Invalid verification code")
    if user.email_verified and user.status == "active":
        return AuthResult(access_token=create_access_token(user.id), user=user)
    if not user.email_verification_code_hash or not user.email_verification_expires_at:
        raise InvalidEmailVerificationCodeError("Invalid verification code")
    if _as_aware(user.email_verification_expires_at) < _now():
        raise InvalidEmailVerificationCodeError("Verification code has expired")
    if user.email_verification_attempts >= _MAX_VERIFICATION_ATTEMPTS:
        raise InvalidEmailVerificationCodeError("Too many invalid verification attempts")
    if not verify_password(code, user.email_verification_code_hash):
        user.email_verification_attempts += 1
        db.commit()
        raise InvalidEmailVerificationCodeError("Invalid verification code")

    user.status = "active"
    user.email_verified = True
    user.email_verified_at = _now()
    user.email_verification_code_hash = None
    user.email_verification_expires_at = None
    user.email_verification_attempts = 0
    db.commit()
    db.refresh(user)

    return AuthResult(access_token=create_access_token(user.id), user=user)


def resend_verification_code(db: Session, *, email: str) -> VerificationCodeResult:
    normalized_email = _normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or user.email_verified:
        return VerificationCodeResult(verification_code=None)

    if user.email_verification_sent_at is not None:
        elapsed = (_now() - _as_aware(user.email_verification_sent_at)).total_seconds()
        if elapsed < settings.email_verification_resend_cooldown_seconds:
            raise VerificationResendCooldownError("Please wait before requesting another code")

    code = _set_verification_code(user)
    send_verification_code(email=user.email, code=code, full_name=user.full_name)
    db.commit()

    return VerificationCodeResult(verification_code=_local_verification_code(code))


def authenticate_user(db: Session, *, email: str, password: str) -> AuthResult:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")
    if user.status != "active" or not user.email_verified:
        raise EmailVerificationRequiredError("Email verification required")

    return AuthResult(access_token=create_access_token(user.id), user=user)


def request_password_reset(db: Session, *, email: str) -> PasswordResetRequestResult:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email, User.status == "active"))
    if user is None:
        return PasswordResetRequestResult(reset_token=None)

    return PasswordResetRequestResult(reset_token=create_password_reset_token(user.id))


def reset_password(db: Session, *, token: str, new_password: str) -> None:
    user_id = decode_password_reset_token(token)
    if user_id is None:
        raise InvalidPasswordResetTokenError("Invalid or expired password reset token")

    user = db.scalar(select(User).where(User.id == user_id, User.status == "active"))
    if user is None:
        raise InvalidPasswordResetTokenError("Invalid or expired password reset token")

    user.password_hash = hash_password(new_password)
    db.commit()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.scalar(select(User).where(User.id == user_id, User.status == "active"))


def list_active_workspace_memberships(db: Session, *, user_id: UUID) -> list[WorkspaceMember]:
    return list(
        db.scalars(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.workspace))
            .join(Workspace)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == "active",
                Workspace.status == "active",
            )
            .order_by(Workspace.created_at.asc())
        )
    )
