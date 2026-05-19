"""Authentication routes — `21_openapi.yaml` /auth/*."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, require_permission
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenData,
    TokenResponse,
    TwoFactorDisableRequest,
    TwoFactorEnabledResponse,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    return await AuthService(session).login(
        username=body.username,
        password=body.password,
        totp_code=body.totp_code,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    return await AuthService(session).refresh(refresh_token=body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await AuthService(session).logout(user_id=user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TwoFactorSetupResponse:
    return await AuthService(session).setup_2fa(user_id=user.user_id)


@router.post("/2fa/verify", response_model=TwoFactorEnabledResponse)
async def verify_2fa(
    body: TwoFactorVerifyRequest,
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TwoFactorEnabledResponse:
    return await AuthService(session).verify_2fa(
        user_id=user.user_id,
        totp_code=body.totp_code,
        secret=body.secret,
    )


@router.post("/2fa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_2fa(
    body: TwoFactorDisableRequest,
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await AuthService(session).disable_2fa(user_id=user.user_id, totp_code=body.totp_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/session/me", include_in_schema=False)
async def session_me(
    user: TokenData = Depends(require_permission("approvals:approve")),
) -> dict:
    """Internal probe: JWT + approvals:approve guard (not in OpenAPI)."""
    return {
        "user_id": str(user.user_id),
        "role": user.role,
        "permissions": user.permissions,
    }
