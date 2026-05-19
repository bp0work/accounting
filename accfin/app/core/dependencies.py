"""FastAPI auth dependencies — `13` §5.7."""

from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
