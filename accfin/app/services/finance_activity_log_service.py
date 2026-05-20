"""Append rows to finance_activity_log — `17` §10.7."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.executive_mail import FinanceActivityLog
from app.repositories.executive_mail import FinanceActivityLogRepository
from app.schemas.executive_mail import FinanceActivityLogCreate


class FinanceActivityLogService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = FinanceActivityLogRepository(session)
        self._tz = ZoneInfo(get_settings().daily_log_timezone)

    async def log(self, entry: FinanceActivityLogCreate) -> FinanceActivityLog:
        now = datetime.now(UTC)
        row = FinanceActivityLog(
            occurred_at=now,
            business_date=now.astimezone(self._tz).date(),
            mailbox_id=entry.mailbox_id,
            case_id=entry.case_id,
            email_id=entry.email_id,
            actor_type=entry.actor_type,
            actor_name=entry.actor_name,
            action=entry.action,
            summary=entry.summary,
            metadata_=entry.metadata,
            created_at=now,
        )
        return await self._repo.append(row)
