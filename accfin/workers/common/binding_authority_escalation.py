"""Binding authority manager escalation — tier 2 (acc) / tier 3 (CFO)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.mail import Email
from app.repositories.case import CaseRepository
from app.services.binding_authority_service import (
    BindingAuthorityService,
    binding_reason_code,
)
from app.services.executive_mail_service import ExecutiveMailService


async def route_binding_authority_escalation(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    tier: int,
    amount: Decimal,
    currency: str,
    extracted_fields: dict[str, str | None] | None,
    extraction_confidence: float,
    actor_name: str,
) -> dict:
    """Escalate pending_approval case to acc (tier 2) or CFO (tier 3)."""
    svc = BindingAuthorityService(session)
    mail = ExecutiveMailService(session)
    cases = CaseRepository(session)

    target = svc.target_email_for_tier(tier)
    amount_str = f"{currency} {amount:,.2f}"
    summary = (
        f"Binding authority Tier {tier} approval required — {amount_str}. "
        f"Review extracted details and Approve, Reject"
        + (", or Escalate to CFO" if tier == 2 else "")
        + "."
    )

    escalation = await mail.escalate_to_manager(
        case=case,
        email=email,
        reason_code=binding_reason_code(tier),
        summary=summary,
        error_detail=summary,
        actor_name=actor_name,
        extracted_fields=extracted_fields,
        extraction_confidence=extraction_confidence,
        escalation_template="manager.escalation.request",
        target_email_override=target,
        include_escalate=tier == 2,
        preserve_case_status=True,
    )

    meta = dict(case.workflow_metadata or {})
    meta.update(
        {
            "binding_authority_pending": True,
            "binding_authority_tier": tier,
            "policy_tier": tier,
            "extracted_fields": extracted_fields or meta.get("extracted_fields"),
            "extraction_confidence": extraction_confidence,
        }
    )
    case.workflow_metadata = meta
    case.status = "pending_approval"
    case.current_approval_tier = tier

    if escalation is None:
        await cases.add_timeline(
            case_id=case.id,
            event_type="exception_raised",
            from_status=case.status,
            to_status="pending_approval",
            actor=actor_name,
            description=summary,
            metadata={"tier": tier, "escalation": "skipped"},
        )
        await session.flush()
        return {
            "status": "pending_approval",
            "case_id": str(case.id),
            "tier": tier,
            "escalation": "skipped",
        }

    await cases.add_timeline(
        case_id=case.id,
        event_type="approval_requested",
        from_status="processing",
        to_status="pending_approval",
        actor=actor_name,
        description=f"Binding authority Tier {tier} — sent to {target}",
        metadata={
            "tier": tier,
            "escalation_id": str(escalation.id),
            "target_email": target,
        },
    )
    await session.flush()
    return {
        "status": "pending_approval",
        "case_id": str(case.id),
        "tier": tier,
        "escalation_id": str(escalation.id),
        "target_email": target,
    }
