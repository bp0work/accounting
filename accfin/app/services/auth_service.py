"""Authentication: login, refresh, logout, 2FA — `05` §3, `13` §5."""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import decrypt_field, encrypt_field
from app.core.exceptions import forbidden, rate_limited, unauthorized
from app.core.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.core.security.password import verify_password
from app.core.security.tokens import hash_refresh_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginResponse,
    TokenResponse,
    TwoFactorEnabledResponse,
    TwoFactorSetupResponse,
    UserResponse,
)
from app.services import totp as totp_service
from app.services.audit_service import AuditService

# In-process login attempt counter (per username) for rate limiting in dev/MVP.
_login_attempts: defaultdict[str, int] = defaultdict(int)

MANDATORY_2FA_ROLE_NAMES = frozenset(
    {"platform_admin", "client_admin", "cfo", "finance_manager"}
)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._settings = get_settings()

    def _user_response(self, user: User, permissions: list[str]) -> UserResponse:
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            role_id=user.role_id,
            role_name=user.role.name if user.role else None,
            department=user.department,
            status=user.status,
            two_factor_enabled=user.two_factor_enabled,
            last_login_at=user.last_login_at,
        )

    def _check_rate_limit(self, username: str) -> None:
        if _login_attempts[username] >= self._settings.login_rate_limit_attempts:
            raise rate_limited()

    def _record_rate_limit_failure(self, username: str) -> None:
        _login_attempts[username] += 1

    def _clear_rate_limit(self, username: str) -> None:
        _login_attempts.pop(username, None)

    async def login(
        self,
        *,
        username: str,
        password: str,
        totp_code: str | None,
        user_ip: str | None = None,
        correlation_id: str | None = None,
    ) -> LoginResponse:
        self._check_rate_limit(username)

        user = await self._users.get_by_username(username)
        if user is None or user.status == "inactive":
            self._record_rate_limit_failure(username)
            raise unauthorized("INVALID_CREDENTIALS", "Username or password incorrect")

        if user.status == "locked" and user.locked_until and user.locked_until > datetime.now(
            UTC
        ):
            raise unauthorized(
                "ACCOUNT_LOCKED",
                "Account is locked due to failed login attempts",
            )

        if not verify_password(user.password_hash, password):
            await self._users.record_failed_login(
                user,
                max_attempts=self._settings.max_failed_login_attempts,
                lockout_minutes=self._settings.lockout_minutes,
            )
            await self._session.commit()
            self._record_rate_limit_failure(username)
            raise unauthorized("INVALID_CREDENTIALS", "Username or password incorrect")

        if user.two_factor_enabled:
            if not totp_code:
                raise unauthorized("TOTP_REQUIRED", "2FA enabled but TOTP code missing")
            if not user.two_factor_secret:
                raise unauthorized("INVALID_TOTP", "TOTP code invalid or expired")
            secret = decrypt_field(user.two_factor_secret)
            if not totp_service.verify_totp(secret=secret, code=totp_code):
                raise unauthorized("INVALID_TOTP", "TOTP code invalid or expired")

        permissions = await self._users.get_permission_codes_for_role(user.role_id)
        access_token, expires_in = create_access_token(
            user_id=user.id,
            role=user.role.name,
            permissions=permissions,
        )
        raw_refresh, _jti, expires_at = create_refresh_token(user_id=user.id)
        await self._users.create_refresh_token(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=expires_at,
        )
        await self._users.record_successful_login(user)
        audit = AuditService(self._session)
        await audit.record(
            action="login",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            user_name=user.display_name,
            user_ip=user_ip,
            after_state={"username": user.username, "role_id": str(user.role_id)},
            correlation_id=correlation_id,
        )
        await self._session.commit()
        self._clear_rate_limit(username)

        return LoginResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=expires_in,
            user=self._user_response(user, permissions),
        )

    async def refresh(self, *, refresh_token: str) -> TokenResponse:
        payload = decode_refresh_token(refresh_token)
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._users.get_refresh_token_by_hash(token_hash)
        if stored is None or not stored.is_valid:
            if stored and stored.revoked_at is not None:
                raise unauthorized("REFRESH_TOKEN_REVOKED", "Token has been revoked")
            raise unauthorized("INVALID_REFRESH_TOKEN", "Token invalid or expired")

        user_id = UUID(payload["sub"])
        user = await self._users.get_by_id(user_id)
        if user is None or user.status != "active":
            raise unauthorized("INVALID_REFRESH_TOKEN", "Token invalid or expired")

        permissions = await self._users.get_permission_codes_for_role(user.role_id)
        access_token, expires_in = create_access_token(
            user_id=user.id,
            role=user.role.name,
            permissions=permissions,
        )
        return TokenResponse(access_token=access_token, expires_in=expires_in)

    async def logout(
        self, *, user_id: UUID, user_ip: str | None = None, correlation_id: str | None = None
    ) -> None:
        user = await self._users.get_by_id(user_id)
        await self._users.revoke_all_refresh_tokens(user_id)
        audit = AuditService(self._session)
        await audit.record(
            action="logout",
            entity_type="user",
            entity_id=user_id,
            user_id=user_id,
            user_name=user.display_name if user else None,
            user_ip=user_ip,
            correlation_id=correlation_id,
        )
        await self._session.commit()

    async def setup_2fa(self, *, user_id: UUID) -> TwoFactorSetupResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise unauthorized("UNAUTHORIZED", "Invalid or expired token")
        if user.two_factor_enabled:
            raise forbidden("CONFLICT", "Two-factor authentication is already enabled")

        secret = totp_service.generate_secret()
        return TwoFactorSetupResponse(
            secret=secret,
            qr_code_uri=totp_service.provisioning_uri(
                secret=secret, username=user.username, email=user.email
            ),
            backup_codes=totp_service.generate_backup_codes(),
        )

    async def verify_2fa(
        self, *, user_id: UUID, totp_code: str, secret: str
    ) -> TwoFactorEnabledResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise unauthorized("UNAUTHORIZED", "Invalid or expired token")
        if not totp_service.verify_totp(secret=secret, code=totp_code):
            raise unauthorized("INVALID_TOTP", "TOTP code invalid or expired")

        await self._users.update_two_factor(
            user, enabled=True, secret=encrypt_field(secret)
        )
        await self._session.commit()
        return TwoFactorEnabledResponse()

    async def disable_2fa(self, *, user_id: UUID, totp_code: str) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise unauthorized("UNAUTHORIZED", "Invalid or expired token")
        if not user.two_factor_enabled or not user.two_factor_secret:
            raise forbidden("CONFLICT", "Two-factor authentication is not enabled")

        secret = decrypt_field(user.two_factor_secret)
        if not totp_service.verify_totp(secret=secret, code=totp_code):
            raise unauthorized("INVALID_TOTP", "TOTP code invalid or expired")

        await self._users.update_two_factor(user, enabled=False, secret=None)
        await self._session.commit()
