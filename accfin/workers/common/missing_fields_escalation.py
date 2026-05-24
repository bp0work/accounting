"""Escalate incomplete AP/AR extraction to manager — `17` §10.4."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.mail import Email
from app.repositories.case import CaseRepository
from app.services.executive_mail_service import ExecutiveMailService


def invoice_extracted_fields(inv: Any) -> dict[str, str | None]:
    """Plain dict of extracted invoice fields for manager email + UI."""
    return {
        "invoice_number": inv.invoice_number,
        "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
        "due_date": str(inv.due_date) if inv.due_date else None,
        "vendor_name": inv.vendor_name,
        "total_amount": inv.total_amount,
        "tax_amount": inv.tax_amount,
        "currency": inv.currency,
        "po_reference": inv.po_reference,
    }


async def route_missing_fields_to_manager(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    missing_fields: list[str],
    extraction_confidence: float,
    extracted_fields: dict[str, str | None],
    actor_name: str,
) -> dict:
    """
    Manager-first escalation when domain worker routes to manual_review for missing data.
    Creates `case_escalations` and queues SMTP via `pending_outbound_emails` with
    `reattach_inbound_attachments` when the source email has inbound files (`17` §10.4).
    """
    svc = ExecutiveMailService(session)
    cases = CaseRepository(session)

    missing_label = ", ".join(missing_fields) if missing_fields else "low extraction confidence"
    summary = f"AP invoice requires manager review — missing or incomplete: {missing_label}"

    escalation = await svc.escalate_to_manager(
        case=case,
        email=email,
        reason_code="INCOMPLETE_EXTRACTION",
        summary=summary,
        error_detail=summary,
        actor_name=actor_name,
        missing_fields=missing_fields,
        extracted_fields=extracted_fields,
        extraction_confidence=extraction_confidence,
        escalation_template="manager.escalation.missing_fields",
    )
    if escalation is None:
        await cases.add_timeline(
            case_id=case.id,
            event_type="exception_raised",
            from_status=case.status,
            to_status="manual_review",
            actor=actor_name,
            description=summary,
            metadata={
                "reason_code": "INCOMPLETE_EXTRACTION",
                "missing_fields": missing_fields,
                "extraction_confidence": extraction_confidence,
                "escalation": "skipped",
            },
        )
        await session.flush()
        return {
            "status": "manual_review",
            "reason": summary,
            "case_id": str(case.id),
            "escalation": "skipped",
        }

    await cases.add_timeline(
        case_id=case.id,
        event_type="exception_raised",
        from_status="manual_review",
        to_status="on_hold",
        actor=actor_name,
        description=f"Escalated to {escalation.target_email}: {summary}",
        metadata={
            "reason_code": "INCOMPLETE_EXTRACTION",
            "escalation_id": str(escalation.id),
            "target_email": escalation.target_email,
            "missing_fields": missing_fields,
            "extraction_confidence": extraction_confidence,
        },
    )
    await session.flush()
    return {
        "status": "escalated_to_manager",
        "case_id": str(case.id),
        "escalation_id": str(escalation.id),
        "target_email": escalation.target_email,
        "missing_fields": missing_fields,
    }
