"""Accounting period calendar — working-day cutoff, period types, settings."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.accounting_errors import PeriodClosedError
from app.models.accounting_period import AccountingPeriod
from app.repositories.system_settings import SystemSettingsRepository
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.finance_activity_log_service import FinanceActivityLogService

AuditFrequency = Literal["annual", "semi_annual", "quarterly"]
PeriodType = Literal["monthly", "audit", "year_end"]

# Singapore public holidays (extend annually). Weekends excluded separately.
SG_PUBLIC_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2025, 1, 1),
        date(2025, 1, 29),
        date(2025, 1, 30),
        date(2025, 4, 18),
        date(2025, 5, 1),
        date(2025, 5, 12),
        date(2025, 6, 7),
        date(2025, 8, 9),
        date(2025, 10, 20),
        date(2025, 12, 25),
        date(2026, 1, 1),
        date(2026, 2, 17),
        date(2026, 2, 18),
        date(2026, 4, 3),
        date(2026, 5, 1),
        date(2026, 5, 27),
        date(2026, 6, 1),
        date(2026, 8, 10),
        date(2026, 11, 8),
        date(2026, 12, 25),
    }
)


def month_end(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in SG_PUBLIC_HOLIDAYS


def add_working_days(start: date, working_days: int) -> date:
    d = start
    added = 0
    while added < working_days:
        d += timedelta(days=1)
        if is_business_day(d):
            added += 1
    return d


def audit_months_for(fye_month: int, audit_frequency: str) -> set[int]:
    if audit_frequency == "semi_annual":
        return {6, fye_month}
    if audit_frequency == "quarterly":
        return {3, 6, 9, fye_month}
    return set()


def resolve_period_type(*, month: int, fye_month: int, audit_frequency: str) -> PeriodType:
    if month == fye_month:
        return "year_end"
    if month in audit_months_for(fye_month, audit_frequency):
        return "audit"
    return "monthly"


def period_display_name(year: int, month: int) -> str:
    names = [
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    return f"{names[month]} {year}"


def period_type_label(period_type: str) -> str:
    return {"monthly": "Monthly", "audit": "Audit", "year_end": "Year-end"}.get(
        period_type, period_type
    )


async def gl_cutoff_working_days(session: AsyncSession) -> int:
    repo = SystemSettingsRepository(session)
    raw = await repo.get_value("gl_cutoff_working_days")
    if raw is None:
        raw = await repo.get_value("gl_posting_cutoff_working_days")
    try:
        return int(raw or "3")
    except ValueError:
        return 3


async def accounting_fye_month(session: AsyncSession) -> int:
    repo = SystemSettingsRepository(session)
    return await repo.get_int("accounting_fye_month", 12)


async def audit_frequency(session: AsyncSession) -> str:
    repo = SystemSettingsRepository(session)
    raw = await repo.get_value("audit_frequency", "annual")
    if raw in ("annual", "semi_annual", "quarterly"):
        return raw
    return "annual"


async def trial_balance_frequency(session: AsyncSession) -> str:
    repo = SystemSettingsRepository(session)
    raw = await repo.get_value("trial_balance_frequency", "monthly")
    return raw if raw in ("monthly", "weekly") else "monthly"


async def ensure_period(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    year: int,
    month: int,
    trial_balance_reviewer: str,
    fye_month: int | None = None,
    audit_freq: str | None = None,
    cutoff_days: int | None = None,
) -> AccountingPeriod:
    fye = fye_month if fye_month is not None else await accounting_fye_month(session)
    freq = audit_freq if audit_freq is not None else await audit_frequency(session)
    days = cutoff_days if cutoff_days is not None else await gl_cutoff_working_days(session)
    ptype = resolve_period_type(month=month, fye_month=fye, audit_frequency=freq)
    cutoff = add_working_days(month_end(year, month), days)

    result = await session.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.period_year == year,
            AccountingPeriod.period_month == month,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.period_type = ptype
        row.gl_cutoff_date = cutoff
        row.trial_balance_reviewer = trial_balance_reviewer
        await session.flush()
        return row

    row = AccountingPeriod(
        tenant_id=tenant_id,
        period_year=year,
        period_month=month,
        period_type=ptype,
        gl_cutoff_date=cutoff,
        trial_balance_reviewer=trial_balance_reviewer,
        status="open",
    )
    session.add(row)
    await session.flush()
    return row


async def accounting_periods_configured(session: AsyncSession) -> bool:
    """Bootstrap mode: no rows → skip period enforcement."""
    count = await session.scalar(select(func.count()).select_from(AccountingPeriod))
    return (count or 0) > 0


async def find_period_for_date(session: AsyncSession, posting_date: date) -> AccountingPeriod | None:
    result = await session.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.period_year == posting_date.year,
            AccountingPeriod.period_month == posting_date.month,
        )
    )
    return result.scalar_one_or_none()


async def assert_period_allows_posting(
    session: AsyncSession,
    posting_date: date,
    *,
    override: bool = False,
    override_reason: str | None = None,
    posted_by: str | None = None,
    case_id: UUID | None = None,
    case_number: str | None = None,
) -> None:
    """
    Enforce GL period status before journal posting.

    - No periods in DB → allow (bootstrap / initial setup).
    - No period for date → allow (period not generated yet).
    - open → allow.
    - review → allow; warning logged to finance_activity_log.
    - closed → PeriodClosedError unless override=True (requires reason + posted_by).
    """
    if not await accounting_periods_configured(session):
        return

    period = await find_period_for_date(session, posting_date)
    if period is None:
        return

    if period.status == "open":
        return

    activity = FinanceActivityLogService(session)
    label = case_number or (str(case_id) if case_id else "—")

    if period.status == "review":
        await activity.log(
            FinanceActivityLogCreate(
                actor_type="system",
                actor_name="gl-period-check",
                action="gl_period_review_warning",
                summary=f"[{label}] Posting to period in review ({posting_date})",
                case_id=case_id,
                metadata={
                    "posting_date": posting_date.isoformat(),
                    "period_id": str(period.id),
                    "period_status": period.status,
                },
            )
        )
        return

    if period.status == "closed":
        if override:
            if not (override_reason and override_reason.strip()):
                raise ValueError("override_reason is required when overriding a closed period")
            if not (posted_by and posted_by.strip()):
                raise ValueError("posted_by is required when overriding a closed period")
            await activity.log(
                FinanceActivityLogCreate(
                    actor_type="manager",
                    actor_name=posted_by,
                    action="gl_period_override_post",
                    summary=f"[{label}] Override post to closed period {period.period_year}-{period.period_month:02d}",
                    case_id=case_id,
                    metadata={
                        "posting_date": posting_date.isoformat(),
                        "period_id": str(period.id),
                        "override_reason": override_reason,
                        "posted_by": posted_by,
                    },
                )
            )
            return
        raise PeriodClosedError(period=period, posting_date=posting_date)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
