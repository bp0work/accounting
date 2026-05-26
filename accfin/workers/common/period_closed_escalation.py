"""Escalate cases blocked by closed GL periods."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_period import AccountingPeriod
from app.models.case import Case
from app.models.mail import Email
from app.repositories.case import CaseRepository
from workers.common.policy_escalation import route_manager_policy_escalation

PERIOD_CLOSED_MESSAGE = (
    "Invoice date falls in a closed GL period. Approve to override and post, "
    "or Reject to return to sender."
)

EXPENSE_PERIOD_CLOSED_MESSAGE = (
    "Expense claim date falls in a closed GL period. Approve to override and post, "
    "or Reject to return to sender."
)


async def route_period_closed_escalation(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    posting_date: date,
    period: AccountingPeriod,
    actor_name: str,
    summary: str | None = None,
) -> dict:
    case.workflow_metadata = {
        **(case.workflow_metadata or {}),
        "error_type": "PERIOD_CLOSED",
        "reason_code": "PERIOD_CLOSED",
        "gl_period_id": str(period.id),
        "posting_date": posting_date.isoformat(),
        "period_year": period.period_year,
        "period_month": period.period_month,
        "period_status": period.status,
    }
    case.status = "manual_review"
    await session.flush()

    extracted = {
        "posting_date": posting_date.isoformat(),
        "period": f"{period.period_year}-{period.period_month:02d}",
        "period_status": period.status,
    }
    return await route_manager_policy_escalation(
        session,
        case,
        email=email,
        reason_code="PERIOD_CLOSED",
        summary=summary or PERIOD_CLOSED_MESSAGE,
        error_detail=summary or PERIOD_CLOSED_MESSAGE,
        actor_name=actor_name,
        extracted_fields=extracted,
    )
