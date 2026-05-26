"""Reopen a closed GL accounting period."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.models.accounting_period import AccountingPeriod
from app.models.user import User
from app.schemas.auth import TokenData
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.accounting_calendar import utcnow
from app.services.finance_activity_log_service import FinanceActivityLogService
from fastapi import status


class GlPeriodReopenService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._activity = FinanceActivityLogService(session)

    async def reopen(self, *, period_id: UUID, user: TokenData) -> AccountingPeriod:
        if user.role not in ("cfo", "client_admin"):
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "CFO or Client Admin role required",
            )

        period = await self._session.get(AccountingPeriod, period_id)
        if period is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Period not found")
        if period.status != "closed":
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "PERIOD_NOT_CLOSED",
                "Only closed periods can be reopened",
            )

        db_user = await self._session.get(User, user.user_id)
        actor = db_user.email if db_user else str(user.user_id)
        reopened_at = utcnow()

        period.status = "open"
        period.gl_closed_at = None
        period.gl_closed_by = None

        await self._activity.log(
            FinanceActivityLogCreate(
                actor_type="manager",
                actor_name=actor,
                action="gl_period_reopened",
                summary=(
                    f"GL period {period.period_year}-{period.period_month:02d} reopened"
                ),
                metadata={
                    "event": "gl_period_reopened",
                    "period_id": str(period.id),
                    "period_year": period.period_year,
                    "period_month": period.period_month,
                    "reopened_by": actor,
                    "reopened_at": reopened_at.isoformat(),
                    "user_id": str(user.user_id),
                },
            )
        )

        await self._session.commit()
        await self._session.refresh(period)
        return period
