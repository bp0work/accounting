"""Password change with Argon2id and history enforcement — `13` §5.2–§5.3."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import (
    PASSWORD_HISTORY_LIMIT,
    hash_password,
    password_matches_history,
    validate_password_policy,
    verify_password,
)
from app.repositories.user import UserRepository


class PasswordService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)
        self._session = session

    async def verify_user_password(self, password_hash: str, password: str) -> bool:
        return verify_password(password_hash, password)

    async def change_password(self, user_id: UUID, new_password: str) -> str:
        """Hash new password, enforce policy and history, append old hash to history."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        validate_password_policy(new_password)
        history = await self._users.get_recent_password_hashes(
            user_id, limit=PASSWORD_HISTORY_LIMIT
        )
        all_hashes = [user.password_hash, *history]
        if password_matches_history(new_password, all_hashes):
            raise ValueError("Password cannot match any of your last 5 passwords")

        await self._users.append_password_history(user_id, user.password_hash)
        new_hash = hash_password(new_password)
        user.password_hash = new_hash
        await self._session.flush()
        return new_hash
