"""Accounting period calendar — working-day cutoff, period status."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_period import AccountingPeriod
from app.repositories.system_settings import SystemSettingsRepository


def month_end(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def add_working_days(start: date, working_days: int) -> date:
    d = start
    added = 0
    while added < working_days:
        d = date.fromordinal(d.toordinal() + 1)
        if d.weekday() < 5:
            added += 1
    return d


async def gl_cutoff_working_days(session: AsyncSession) -> int:
    repo = SystemSettingsRepository(session)
    raw = await repo.get_value("gl_posting_cutoff_working_days")
    try:
        return int(raw or "3")
    except ValueError:
        return 3


async def ensure_period(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    year: int,
    month: int,
    trial_balance_reviewer: str,
) -> AccountingPeriod:
    result = await session.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.period_year == year,
            AccountingPeriod.period_month == month,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    days = await gl_cutoff_working_days(session)
    cutoff = add_working_days(month_end(year, month), days)
    row = AccountingPeriod(
        tenant_id=tenant_id,
        period_year=year,
        period_month=month,
        gl_cutoff_date=cutoff,
        trial_balance_reviewer=trial_balance_reviewer,
        status="open",
    )
    session.add(row)
    await session.flush()
    return row


async def assert_period_allows_posting(session: AsyncSession, *, tenant_id: UUID, entry_date: date) -> None:
    """Reject journal posting when GL period is not open."""
    result = await session.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.period_year == entry_date.year,
            AccountingPeriod.period_month == entry_date.month,
        )
    )
    period = result.scalar_one_or_none()
    if period is None or period.status != "open":
        from app.core.exceptions import AppHTTPException
        from fastapi import status

        raise AppHTTPException(
            status.HTTP_409_CONFLICT,
            "GL_PERIOD_CLOSED",
            "Accounting period is not open for posting; escalate to Finance Manager.",
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
