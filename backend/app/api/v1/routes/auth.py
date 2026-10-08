from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.auth import (
    AuthTokenResponse,
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationCodeRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.services.auth_service import (
    DuplicateEmailError,
    EmailVerificationRequiredError,
    InvalidCredentialsError,
    InvalidEmailVerificationCodeError,
    InvalidPasswordResetTokenError,
    InvalidRegistrationError,
    VerificationResendCooldownError,
    authenticate_user,
    list_active_workspace_memberships,
    register_user,
    request_password_reset,
    resend_verification_code,
    reset_password,
    verify_email,
)
from app.services.email_service import EmailDeliveryError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_202_ACCEPTED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    try:
        result = register_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidRegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the verification email. Please try again later.",
        ) from exc

    return RegisterResponse(
        message="Verification code sent to email",
        verification_code=result.verification_code,
    )


@router.post("/verify-email", response_model=AuthTokenResponse)
def verify_user_email(
    payload: VerifyEmailRequest, db: Session = Depends(get_db)
) -> AuthTokenResponse:
    try:
        result = verify_email(db, email=payload.email, code=payload.code)
    except InvalidEmailVerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidRegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return AuthTokenResponse(access_token=result.access_token, user=result.user)


@router.post("/resend-verification-code", response_model=RegisterResponse)
def resend_user_verification_code(
    payload: ResendVerificationCodeRequest, db: Session = Depends(get_db)
) -> RegisterResponse:
    try:
        result = resend_verification_code(db, email=payload.email)
    except VerificationResendCooldownError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except InvalidRegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the verification email. Please try again later.",
        ) from exc

    return RegisterResponse(
        message="If the email requires verification, a new code has been sent.",
        verification_code=result.verification_code,
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    try:
        result = authenticate_user(db, email=payload.email, password=payload.password)
    except EmailVerificationRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return AuthTokenResponse(access_token=result.access_token, user=result.user)


@router.post("/logout", response_model=MessageResponse)
def logout(user: User = Depends(get_current_user)) -> MessageResponse:
    return MessageResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    try:
        result = request_password_reset(db, email=payload.email)
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the password reset email. Please try again later.",
        ) from exc
    return ForgotPasswordResponse(
        message="If the email exists, a password reset link has been sent.",
        reset_token=result.reset_token,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_user_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    try:
        reset_password(db, token=payload.token, new_password=payload.new_password)
    except InvalidPasswordResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return MessageResponse(message="Password reset successfully")


@router.get("/me", response_model=CurrentUserResponse)
def current_user(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CurrentUserResponse:
    memberships = list_active_workspace_memberships(db, user_id=user.id)
    return CurrentUserResponse(user=user, workspaces=memberships)
