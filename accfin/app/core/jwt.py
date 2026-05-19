"""JWT access and refresh tokens — `13` §5.4."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import unauthorized


def _settings():
    return get_settings()


def create_access_token(
    *,
    user_id: UUID,
    role: str,
    permissions: list[str],
) -> tuple[str, int]:
    settings = _settings()
    expires_delta = timedelta(minutes=settings.jwt_access_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "permissions": permissions,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(*, user_id: UUID) -> tuple[str, UUID, datetime]:
    settings = _settings()
    jti = uuid4()
    expires_delta = timedelta(days=settings.jwt_refresh_expire_days)
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    settings = _settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except InvalidTokenError as exc:
        raise unauthorized("UNAUTHORIZED", "Invalid or expired token") from exc

    if expected_type and payload.get("type") != expected_type:
        raise unauthorized("UNAUTHORIZED", "Invalid token type")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return decode_token(token, expected_type="refresh")
