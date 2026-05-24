"""Manager escalation helpers for PO and travel policy gates."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.mail import Email
from app.repositories.case import CaseRepository
from app.services.executive_mail_service import ExecutiveMailService

PO_NOT_FOUND_MESSAGE = (
    "No PO found for this invoice. Approve to proceed with posting, "
    "or Reject to return to sender requesting PO reference"
)

PO_MISMATCH_MESSAGE = (
    "Invoice does not match the purchase order. Approve to proceed with posting, "
    "or Reject to return to sender"
)

TRAVEL_REQUEST_MISSING_MESSAGE = (
    "No travel request found for this expense claim. Approve to proceed, "
    "or Reject to return to sender"
)


async def route_manager_policy_escalation(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    reason_code: str,
    summary: str,
    error_detail: str,
    actor_name: str,
    extracted_fields: dict[str, str | None] | None = None,
    extraction_confidence: float | None = None,
) -> dict:
    """Escalate to manager with Approve/Reject links (`manager.escalation.request`)."""
    svc = ExecutiveMailService(session)
    cases = CaseRepository(session)

    escalation = await svc.escalate_to_manager(
        case=case,
        email=email,
        reason_code=reason_code,
        summary=summary,
        error_detail=error_detail,
        actor_name=actor_name,
        extracted_fields=extracted_fields,
        extraction_confidence=extraction_confidence,
        escalation_template="manager.escalation.request",
    )
    if escalation is None:
        await cases.add_timeline(
            case_id=case.id,
            event_type="exception_raised",
            from_status=case.status,
            to_status="manual_review",
            actor=actor_name,
            description=summary,
            metadata={"reason_code": reason_code, "escalation": "skipped"},
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
        from_status=case.status,
        to_status="on_hold",
        actor=actor_name,
        description=f"Escalated to {escalation.target_email}: {summary}",
        metadata={
            "reason_code": reason_code,
            "escalation_id": str(escalation.id),
            "target_email": escalation.target_email,
        },
    )
    await session.flush()
    return {
        "status": "escalated_to_manager",
        "case_id": str(case.id),
        "escalation_id": str(escalation.id),
        "target_email": escalation.target_email,
        "reason": summary,
    }


async def route_po_not_found_escalation(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    extracted_fields: dict[str, str | None],
    extraction_confidence: float,
    actor_name: str,
    po_validation: dict[str, Any],
) -> dict:
    case.workflow_metadata = {
        **(case.workflow_metadata or {}),
        "po_validation": po_validation,
        "extracted_fields": extracted_fields,
        "extraction_confidence": extraction_confidence,
        "error_type": "PO_NOT_FOUND",
    }
    case.status = "manual_review"
    await session.flush()
    return await route_manager_policy_escalation(
        session,
        case,
        email=email,
        reason_code="PO_NOT_FOUND",
        summary=PO_NOT_FOUND_MESSAGE,
        error_detail=PO_NOT_FOUND_MESSAGE,
        actor_name=actor_name,
        extracted_fields=extracted_fields,
        extraction_confidence=extraction_confidence,
    )


async def route_po_mismatch_escalation(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    extracted_fields: dict[str, str | None],
    extraction_confidence: float,
    actor_name: str,
    po_validation: dict[str, Any],
) -> dict:
    case.workflow_metadata = {
        **(case.workflow_metadata or {}),
        "po_validation": po_validation,
        "extracted_fields": extracted_fields,
        "extraction_confidence": extraction_confidence,
        "error_type": "PO_MISMATCH",
    }
    case.status = "manual_review"
    await session.flush()
    return await route_manager_policy_escalation(
        session,
        case,
        email=email,
        reason_code="PO_MISMATCH",
        summary=PO_MISMATCH_MESSAGE,
        error_detail=PO_MISMATCH_MESSAGE,
        actor_name=actor_name,
        extracted_fields=extracted_fields,
        extraction_confidence=extraction_confidence,
    )


async def route_travel_request_escalation(
    session: AsyncSession,
    case: Case,
    *,
    email: Email | None,
    claim_summary: dict[str, str | None],
    extraction_confidence: float,
    actor_name: str,
    travel_validation: dict[str, Any],
) -> dict:
    case.workflow_metadata = {
        **(case.workflow_metadata or {}),
        "travel_request_validation": travel_validation,
        "error_type": "TRAVEL_REQUEST_NOT_FOUND",
    }
    case.status = "manual_review"
    await session.flush()
    return await route_manager_policy_escalation(
        session,
        case,
        email=email,
        reason_code="TRAVEL_REQUEST_NOT_FOUND",
        summary=TRAVEL_REQUEST_MISSING_MESSAGE,
        error_detail=TRAVEL_REQUEST_MISSING_MESSAGE,
        actor_name=actor_name,
        extracted_fields=claim_summary,
        extraction_confidence=extraction_confidence,
    )
