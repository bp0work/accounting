"""Derived fields for finance oversight UI — status, stage, errors, activity."""

from __future__ import annotations

from datetime import datetime

from app.models.case import Case

EXCEPTION_STATUSES = frozenset({"exception", "manual_review", "on_hold", "rejected"})
AP_CASE_TYPES = frozenset({"ap_invoice", "ap_po_validation", "ap_payment_proposal"})
AR_CASE_TYPES = frozenset({"ar_invoice", "ar_payment_advice", "ar_statement"})


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


def processing_stage(case: Case) -> str:
    meta = case.workflow_metadata or {}
    stage = meta.get("current_stage")
    if isinstance(stage, str) and stage:
        if stage in ("classification", "intake"):
            return "classified" if case.status != "inbound" else "intake"
        if stage in ("processing", "extraction"):
            return "processing"
        return stage

    status = case.status
    if status == "inbound":
        return "intake"
    if status == "classified":
        return "classified"
    if status in ("processing", "pending_approval", "approved"):
        return "processing"
    if status in EXCEPTION_STATUSES:
        return "exception"
    if status in ("posted", "completed"):
        return "completed"
    return status


def error_reason(case: Case) -> str | None:
    if case.status not in EXCEPTION_STATUSES and case.status != "on_hold":
        return None
    meta = case.workflow_metadata or {}
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
    return None


def last_activity_at(case: Case) -> datetime:
    if case.timeline:
        return max(entry.created_at for entry in case.timeline)
    return case.updated_at or case.created_at
