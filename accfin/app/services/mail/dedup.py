"""Duplicate detection — Message-ID only — `02` §7, `17` §2.1."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail import Email


class DedupResult:
    def __init__(
        self,
        *,
        is_duplicate: bool,
        duplicate_of_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        self.is_duplicate = is_duplicate
        self.duplicate_of_id = duplicate_of_id
        self.reason = reason


class EmailDedupService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(self, *, message_id: str, content_hash: str | None = None) -> DedupResult:
        _ = content_hash  # retained for API compatibility; dedupe is Message-ID only
        by_message = await self._session.execute(
            select(Email).where(Email.message_id == message_id)
        )
        existing = by_message.scalar_one_or_none()
        if existing is not None:
            return DedupResult(
                is_duplicate=True,
                duplicate_of_id=existing.id,
                reason="message_id",
            )

        return DedupResult(is_duplicate=False)
