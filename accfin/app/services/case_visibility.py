"""Derived fields for finance oversight UI — status, stage, errors, activity."""

from __future__ import annotations

from datetime import datetime

from app.models.case import Case

EXCEPTION_STATUSES = frozenset({"exception", "manual_review", "on_hold", "rejected"})
REJECTED_STATUSES = frozenset({"rejected", "case_rejected"})
AP_CASE_TYPES = frozenset({"ap_invoice", "ap_po_validation", "ap_payment_proposal"})
AR_CASE_TYPES = frozenset({"ar_invoice", "ar_payment_advice", "ar_statement"})

# High-level buckets for finance UI (group → human-readable status).
STATUS_GROUP_LABELS: dict[str, str] = {
    "intake": "Intake",
    "queued": "Queued",
    "processing": "Processing",
    "parsing_review": "Parsing review",
    "approval": "Approval",
    "complete": "Complete",
    "attention": "Needs attention",
    "rejected": "Rejected",
}

_STATUS_DISPLAY_LABELS: dict[str, str] = {
    "inbound": "Received",
    "classified": "Waiting for worker",
    "processing": "In progress",
    "validation": "Validating",
    "pending_confirmation": "Confirm extracted fields",
    "pending_approval": "Awaiting approval",
    "approved": "Approved",
    "posted": "Posted to GL",
    "completed": "Completed",
    "exception": "Exception",
    "manual_review": "Manual review",
    "on_hold": "On hold",
    "rejected": "Rejected",
    "case_rejected": "Case rejected",
    "journal_entry_created": "Journal draft created",
    "journal_pending_approval": "Journal awaiting approval",
    "journal_posted": "Journal posted",
    "case_closed": "Closed",
    "validation_completed": "Validation complete",
}

_WORKFLOW_STEP_LABELS: dict[str, str] = {
    "classification": "Classifying",
    "intake": "Intake",
    "parsing": "Parsing document",
    "parsing_confirmation": "Parsing confirmation",
    "processing": "Processing",
    "extraction": "Extracting fields",
    "journal_created": "Journal created",
    "completed": "Completed",
}

# DB statuses where workflow_metadata.current_stage must not override display.
_STATUS_AUTHORITATIVE = frozenset(
    {
        "inbound",
        "classified",
        "pending_confirmation",
        "pending_approval",
        "approved",
        "posted",
        "completed",
        "case_closed",
        "journal_posted",
        "validation_completed",
        "case_rejected",
        "rejected",
    }
    | REJECTED_STATUSES
)


def _extracted_field(workflow_metadata: dict, field: str) -> str | None:
    extracted = workflow_metadata.get("extracted_fields")
    if not isinstance(extracted, dict):
        return None
    val = extracted.get(field)
    if val is None or val == "":
        return None
    return str(val)


def client_vendor_name(case: Case) -> str | None:
    """Display name for Client / Vendor column — issuer for AP, customer for AR."""
    meta = case.workflow_metadata or {}
    if case.type in AP_CASE_TYPES:
        vendor = _extracted_field(meta, "vendor_name")
        if vendor:
            return vendor
    if case.type in AR_CASE_TYPES:
        customer = _extracted_field(meta, "customer_name")
        if customer:
            return customer
    return case.counterparty_name


def case_status_group(case: Case) -> str:
    """Machine id for UI grouping — derived from authoritative ``case.status``."""
    status = case.status
    if status == "inbound":
        return "intake"
    if status == "classified":
        return "queued"
    if status in ("processing", "validation", "journal_entry_created"):
        return "processing"
    if status == "pending_confirmation":
        return "parsing_review"
    if status in ("pending_approval", "approved", "journal_pending_approval"):
        return "approval"
    if status in (
        "posted",
        "completed",
        "case_closed",
        "journal_posted",
        "validation_completed",
    ):
        return "complete"
    if status in EXCEPTION_STATUSES:
        return "attention"
    if status in REJECTED_STATUSES:
        return "rejected"
    return "processing"


def case_status_group_label(case: Case) -> str:
    return STATUS_GROUP_LABELS.get(case_status_group(case), "Processing")


def _workflow_step(case: Case) -> str | None:
    meta = case.workflow_metadata or {}
    stage = meta.get("current_stage")
    if isinstance(stage, str) and stage:
        return stage
    return None


def case_status_label(case: Case) -> str:
    """Human-readable status — DB status first; worker step only when consistent."""
    status = case.status
    base = _STATUS_DISPLAY_LABELS.get(status, status.replace("_", " ").title())

    if status == "on_hold":
        meta = case.workflow_metadata or {}
        if meta.get("escalation_pending"):
            return "On hold — awaiting escalation response"
        code = meta.get("reason_code") or meta.get("error_type")
        if code:
            return f"On hold ({code})"

    if status in _STATUS_AUTHORITATIVE:
        return base

    step = _workflow_step(case)
    if step and status in ("processing", "validation"):
        return _WORKFLOW_STEP_LABELS.get(step, step.replace("_", " ").title())

    if status in EXCEPTION_STATUSES:
        if step and step not in ("classification", "intake"):
            return _WORKFLOW_STEP_LABELS.get(step, step.replace("_", " ").title())
        return base

    return base


def processing_stage(case: Case) -> str:
    """Legacy step field — kept for API compat; aligned with group/label."""
    group = case_status_group(case)
    if group == "intake":
        return "intake"
    if group == "queued":
        return "classified"
    if group == "rejected":
        return "rejected" if case.status == "rejected" else "case_rejected"
    if group == "complete":
        return "completed"
    if group == "attention":
        step = _workflow_step(case)
        if not step or step in ("classification", "intake"):
            return "exception"
        if step in ("processing", "extraction"):
            return "processing"
        return step
    if group == "parsing_review":
        return "parsing_confirmation"
    if group == "approval":
        return "processing"
    step = _workflow_step(case)
    if step:
        if step in ("classification", "intake"):
            return "classified"
        if step in ("processing", "extraction"):
            return "processing"
        return step
    if case.status == "classified":
        return "classified"
    if case.status in ("processing", "pending_approval", "approved"):
        return "processing"
    return case.status


def error_reason(case: Case) -> str | None:
    meta = case.workflow_metadata or {}
    if case.status in REJECTED_STATUSES:
        for key in ("error_message", "error_reason", "reason_code", "reason", "error_type"):
            val = meta.get(key)
            if val:
                return str(val)
        return None
    if case.status not in EXCEPTION_STATUSES and case.status != "on_hold":
        return None
    for key in ("error_message", "error_reason", "reason_code", "reason", "error_type"):
        val = meta.get(key)
        if val:
            return str(val)
    if case.status in ("manual_review", "on_hold"):
        parts: list[str] = []
        missing = meta.get("missing_fields")
        if isinstance(missing, list) and missing:
            parts.append(f"Missing fields: {', '.join(str(m) for m in missing)}")
        conf = meta.get("extraction_confidence")
        if conf is not None:
            parts.append(f"Extraction confidence: {conf}")
        if parts:
            return " · ".join(parts)
    if case.status == "manual_review":
        return meta.get("reason") or "Routed to manual review"
    if case.status == "on_hold" and meta.get("escalation_pending"):
        return meta.get("error_reason") or "Awaiting manager escalation response"
    return None


def status_reason(case: Case) -> str | None:
    reason = error_reason(case)
    if reason:
        return reason
    if case.status in ("posted", "completed"):
        return "Processing completed successfully"
    if case.status == "pending_approval":
        tier = case.current_approval_tier
        return f"Awaiting approval (tier {tier})" if tier else "Awaiting approval"
    if case.status == "classified":
        return "Classified — queued for domain worker"
    if case.status == "processing":
        return "Domain worker processing in progress"
    if case.status == "pending_confirmation":
        return "Review extracted fields and confirm or reject parsing"
    if case.status in REJECTED_STATUSES:
        return "Case was rejected and will not continue processing"
    return None


def last_activity_at(case: Case) -> datetime:
    if case.timeline:
        return max(entry.created_at for entry in case.timeline)
    return case.updated_at or case.created_at
