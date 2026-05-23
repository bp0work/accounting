"""Shared processing-failure routing — `17` §10.4."""

from __future__ import annotations

from app.models.case import Case
from app.models.mail import Email
from app.services.executive_mail_service import ExecutiveMailService
from sqlalchemy.ext.asyncio import AsyncSession


async def route_processing_failure(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    reason_code: str,
    summary: str,
    error_detail: str,
    actor_name: str,
) -> dict:
    """Escalate to manager; never notify sender directly."""
    svc = ExecutiveMailService(session)
    escalation = await svc.escalate_to_manager(
        case=case,
        email=email,
        reason_code=reason_code,
        summary=summary,
        error_detail=error_detail,
        actor_name=actor_name,
    )
    if escalation is None:
        case.status = "manual_review"
        await session.flush()
        return {
            "status": "manual_review",
            "reason": error_detail,
            "case_id": str(case.id),
            "escalation": "skipped",
        }
    return {
        "status": "escalated_to_manager",
        "reason": error_detail,
        "case_id": str(case.id),
        "escalation_id": str(escalation.id),
        "target_email": escalation.target_email,
    }
