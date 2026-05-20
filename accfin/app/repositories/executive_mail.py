"""Executive email SOP persistence — `06` §7.4–§7.6."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.executive_mail import CaseEscalation, FinanceActivityLog
from app.models.mail import MailGatewayConfig


class FinanceActivityLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, row: FinanceActivityLog) -> FinanceActivityLog:
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_business_date(self, business_date: date) -> list[FinanceActivityLog]:
        result = await self._session.execute(
            select(FinanceActivityLog)
            .where(FinanceActivityLog.business_date == business_date)
            .order_by(FinanceActivityLog.occurred_at.asc())
        )
        return list(result.scalars().all())


class CaseEscalationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, escalation_id: UUID) -> CaseEscalation | None:
        result = await self._session.execute(
            select(CaseEscalation).where(CaseEscalation.id == escalation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> CaseEscalation | None:
        result = await self._session.execute(
            select(CaseEscalation).where(CaseEscalation.response_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def create(self, row: CaseEscalation) -> CaseEscalation:
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_mailbox_by_email(self, email: str) -> MailGatewayConfig | None:
        result = await self._session.execute(
            select(MailGatewayConfig).where(MailGatewayConfig.email_address == email)
        )
        return result.scalar_one_or_none()
