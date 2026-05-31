"""Shared GL period gate before journal posting in domain workers."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.accounting_errors import PeriodClosedError
from app.models.case import Case
from app.models.mail import Email
from app.services.accounting_calendar import assert_period_allows_posting
from workers.common.period_closed_escalation import (
    EXPENSE_PERIOD_CLOSED_MESSAGE,
    PERIOD_CLOSED_MESSAGE,
    route_period_closed_escalation,
)


def gl_override_from_message(case: Case, message: dict) -> tuple[bool, str | None, str | None]:
    meta = case.workflow_metadata or {}
    override = bool(
        message.get("gl_period_override")
        or meta.get("gl_period_override")
    )
    reason = message.get("gl_period_override_reason") or meta.get("gl_period_override_reason")
    posted_by = message.get("gl_period_posted_by") or meta.get("gl_period_posted_by")
    return override, reason, posted_by


async def ensure_gl_period_allows_posting(
    session: AsyncSession,
    case: Case,
    message: dict,
    *,
    posting_date: date,
    email: Email | None,
    actor_name: str,
    expense: bool = False,
    force_new_escalation: bool = False,
) -> dict | None:
    """
    Run period check. Returns escalation result dict if blocked; None if posting may proceed.
    """
    override, reason, posted_by = gl_override_from_message(case, message)
    try:
        await assert_period_allows_posting(
            session,
            posting_date,
            override=override,
            override_reason=reason,
            posted_by=posted_by,
            case_id=case.id,
            case_number=case.case_number,
        )
        return None
    except PeriodClosedError as exc:
        if force_new_escalation:
            from app.services.executive_mail_service import ExecutiveMailService

            svc = ExecutiveMailService(session)
            if await svc.cancel_pending_escalation(case.id):
                meta = dict(case.workflow_metadata or {})
                meta["escalation_pending"] = False
                meta.pop("escalation_id", None)
                case.workflow_metadata = meta
                await session.flush()
        return await route_period_closed_escalation(
            session,
            case,
            email=email,
            posting_date=posting_date,
            period=exc.period,
            actor_name=actor_name,
            summary=EXPENSE_PERIOD_CLOSED_MESSAGE if expense else PERIOD_CLOSED_MESSAGE,
        )
    except ValueError as exc:
        return {
            "status": "manual_review",
            "case_id": str(case.id),
            "error": str(exc),
        }
