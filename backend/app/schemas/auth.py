from pydantic import AliasChoices, BaseModel, ConfigDict, Field, AliasPath

from app.schemas.user import UserRead
from app.schemas.workspace import WorkspaceMembershipRead


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("full_name", "fullName", AliasPath("user", "fullName")),
    )
    company_name: str | None = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("company_name", "companyName", AliasPath("company", "name")),
    )
    role: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("role", "roleName"),
    )
    confirm_password: str | None = Field(default=None, max_length=128)
    terms_accepted: bool | None = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class RegisterResponse(BaseModel):
    message: str
    verification_code: str | None = None


class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class CurrentUserResponse(BaseModel):
    user: UserRead
    workspaces: list[WorkspaceMembershipRead]
