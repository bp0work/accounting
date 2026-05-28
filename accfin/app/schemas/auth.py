"""Auth request/response schemas — `21_openapi.yaml` components."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)
    totp_code: str | None = Field(default=None, min_length=6, max_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class TwoFactorVerifyRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=6)
    secret: str


class TwoFactorDisableRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=100)
    new_password: str = Field(min_length=8, max_length=100)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    email: EmailStr
    role_id: UUID
    role_name: str | None = None
    department: str | None = None
    status: str
    two_factor_enabled: bool
    last_login_at: datetime | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


class TwoFactorEnabledResponse(BaseModel):
    two_factor_enabled: bool = True


class ActiveSessionResponse(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class TokenData(BaseModel):
    user_id: UUID
    role: str
    permissions: list[str]
