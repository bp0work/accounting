"""Shared processing-failure routing — `17` §10.4."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.mail import Email
from app.repositories.case import CaseRepository
from app.services.executive_mail_service import ExecutiveMailService


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
    cases = CaseRepository(session)
    escalation = await svc.escalate_to_manager(
        case=case,
        email=email,
        reason_code=reason_code,
        summary=summary,
        error_detail=error_detail,
        actor_name=actor_name,
    )
    if escalation is None:
        from_status = case.status
        case.status = "manual_review"
        await cases.add_timeline(
            case_id=case.id,
            event_type="exception_raised",
            from_status=from_status,
            to_status="manual_review",
            actor=actor_name,
            description=error_detail,
            metadata={"reason_code": reason_code, "summary": summary},
        )
        await session.flush()
        return {
            "status": "manual_review",
            "reason": error_detail,
            "case_id": str(case.id),
            "escalation": "skipped",
        }

    await cases.add_timeline(
        case_id=case.id,
        event_type="exception_raised",
        from_status=case.status,
        to_status="on_hold",
        actor=actor_name,
        description=f"Escalated to {escalation.target_email}: {error_detail}",
        metadata={
            "reason_code": reason_code,
            "escalation_id": str(escalation.id),
            "target_email": escalation.target_email,
            "summary": summary,
        },
    )
    await session.flush()
    return {
        "status": "escalated_to_manager",
        "reason": error_detail,
        "case_id": str(case.id),
        "escalation_id": str(escalation.id),
        "target_email": escalation.target_email,
    }
