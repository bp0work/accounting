"""FastAPI auth dependencies — `13` §5.7."""

from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.constants.finance_setup import FINANCE_SETUP_ROLE_NAMES
from app.core.exceptions import AppHTTPException
from app.core.jwt import decode_access_token
from app.schemas.auth import TokenData

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenData:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppHTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "No valid token provided",
        )
    payload = decode_access_token(credentials.credentials)
    return TokenData(
        user_id=UUID(str(payload["sub"])),
        role=str(payload["role"]),
        permissions=list(payload.get("permissions") or []),
    )


def require_client_admin():
    """Client Admin UI — `tenant:admin` permission (client_admin role)."""

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role != "client_admin" and "tenant:admin" not in user.permissions:
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "INSUFFICIENT_PERMISSION",
                "Client administrator access is required.",
            )
        return user

    return _check


def require_finance_setup_access():
    """Finance UI setup: counterparty accounts, agreements, accounting calendar."""

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role in FINANCE_SETUP_ROLE_NAMES:
            return user
        if "tenant:admin" in user.permissions:
            return user
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN,
            "INSUFFICIENT_PERMISSION",
            "Finance setup access is required.",
        )

    return _check


def require_gl_posting_override():
    """CFO, Finance Manager, or Client Admin — retroactive GL period posting."""

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role in ("client_admin", "cfo", "finance_manager"):
            return user
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN,
            "INSUFFICIENT_PERMISSION",
            "CFO, Finance Manager, or Client Admin access is required.",
        )

    return _check


def require_period_reopen():
    """CFO or Client Admin — reopen a closed GL period."""

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role in ("cfo", "client_admin"):
            return user
        if "tenant:admin" in user.permissions:
            return user
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN,
            "INSUFFICIENT_PERMISSION",
            "CFO or Client Admin access is required.",
        )

    return _check


def require_permission(permission_code: str):
    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if permission_code not in user.permissions:
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "INSUFFICIENT_PERMISSION",
                f"Permission '{permission_code}' is required for this action.",
            )
        return user

    return _check
