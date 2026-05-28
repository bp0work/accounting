"""User and RBAC data access."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rbac import Permission, RolePermission
from app.models.user import PasswordHistory, RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_permission_codes_for_role(self, role_id: UUID) -> list[str]:
        result = await self._session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.code)
        )
        return list(result.scalars().all())

    async def record_successful_login(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        user.status = "active"
        await self._session.flush()

    async def record_failed_login(
        self, user: User, *, max_attempts: int, lockout_minutes: int
    ) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.status = "locked"
            user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
        await self._session.flush()

    async def get_recent_password_hashes(self, user_id: UUID, limit: int = 5) -> list[str]:
        result = await self._session.execute(
            select(PasswordHistory.password_hash)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def append_password_history(self, user_id: UUID, password_hash: str) -> None:
        self._session.add(PasswordHistory(user_id=user_id, password_hash=password_hash))
        await self._session.flush()

    async def create_refresh_token(
        self, *, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_all_refresh_tokens(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for token in result.scalars().all():
            token.revoked_at = now
        await self._session.flush()

    async def list_active_refresh_tokens(self, user_id: UUID) -> list[RefreshToken]:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_two_factor(
        self,
        user: User,
        *,
        enabled: bool,
        secret: str | None,
    ) -> None:
        user.two_factor_enabled = enabled
        user.two_factor_secret = secret
        await self._session.flush()
