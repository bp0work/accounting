"""Mail gateway data access."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mail import Email, MailGatewayConfig


class MailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_pollable_mailboxes(self) -> list[MailGatewayConfig]:
        result = await self._session.execute(
            select(MailGatewayConfig).where(
                MailGatewayConfig.mailbox_mode == "executive_agent",
                MailGatewayConfig.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def get_mailbox_by_id(self, mailbox_id: UUID) -> MailGatewayConfig | None:
        result = await self._session.execute(
            select(MailGatewayConfig).where(MailGatewayConfig.id == mailbox_id)
        )
        return result.scalar_one_or_none()

    async def list_emails(
        self, *, limit: int = 50, cursor_received_at=None
    ) -> list[Email]:
        stmt = select(Email).order_by(Email.received_at.desc()).limit(limit)
        if cursor_received_at is not None:
            stmt = stmt.where(Email.received_at < cursor_received_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_email(self, email_id: UUID) -> Email | None:
        result = await self._session.execute(
            select(Email)
            .options(selectinload(Email.attachments))
            .where(Email.id == email_id)
        )
        return result.scalar_one_or_none()

    async def count_emails_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Email.status, func.count()).group_by(Email.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def list_mailboxes(self) -> list[MailGatewayConfig]:
        result = await self._session.execute(
            select(MailGatewayConfig).order_by(MailGatewayConfig.email_address)
        )
        return list(result.scalars().all())

    async def get_duplicates_for(self, email_id: UUID) -> list[Email]:
        result = await self._session.execute(
            select(Email).where(Email.duplicate_of_id == email_id)
        )
        return list(result.scalars().all())
