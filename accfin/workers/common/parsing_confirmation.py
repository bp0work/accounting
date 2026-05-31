"""Parsing confirmation pause/resume — `0.14.25`."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.case import Case
from app.models.executive_mail import PendingOutboundEmail
from app.models.mail import Email, MailGatewayConfig
from app.repositories.case import CaseRepository
from app.schemas.hermes import ExtractedInvoice
from app.services.executive_mail_service import ExecutiveMailService
from app.services.outbound_mail_service import OutboundMailService
from workers.common.missing_fields_escalation import invoice_extracted_fields

PARSING_CONFIRMATION_EXECUTIVE_ADDRESSES = frozenset(
    {
        "accap.mmlogistix@bp0.work",
        "accar.mmlogistix@bp0.work",
        "accexp.mmlogistix@bp0.work",
    }
)

PARSING_CONFIRMATION_NOTIFY_TO = (
    "acc.mmlogistix@bp0.work",
    "fin.mmlogistix@bp0.work",
)

SENDER_MAILBOX = "acc.mmlogistix@bp0.work"


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_extracted_fields(raw: dict[str, Any]) -> dict[str, str | None]:
    """Canonical field dict for UI, workers, and notification email."""
    doc_num = raw.get("document_number") or raw.get("invoice_number")
    doc_date = raw.get("document_date") or raw.get("invoice_date")
    gst = raw.get("gst_amount") or raw.get("tax_amount")
    sender = raw.get("sender_validated")
    if isinstance(sender, bool):
        sender_str = "true" if sender else "false"
    elif sender is None:
        sender_str = "false"
    else:
        sender_str = (
            "true" if str(sender).strip().lower() in ("true", "1", "yes") else "false"
        )
    out = {
        "document_type": str(raw.get("document_type") or "invoice"),
        "document_number": str(doc_num).strip() if doc_num else None,
        "document_date": str(doc_date).strip() if doc_date else None,
        "due_date": str(raw.get("due_date")).strip() if raw.get("due_date") else None,
        "vendor_name": str(raw.get("vendor_name")).strip() if raw.get("vendor_name") else None,
        "total_amount": str(raw.get("total_amount")).strip() if raw.get("total_amount") else None,
        "gst_amount": str(gst).strip() if gst else None,
        "currency": str(raw.get("currency") or "SGD"),
        "exchange_rate": str(raw.get("exchange_rate")).strip() if raw.get("exchange_rate") else None,
        "sgd_amount": str(raw.get("sgd_amount")).strip() if raw.get("sgd_amount") else None,
        "payment_terms": str(raw.get("payment_terms")).strip() if raw.get("payment_terms") else None,
        "sender_validated": sender_str,
        "invoice_number": str(doc_num).strip() if doc_num else None,
        "invoice_date": str(doc_date).strip() if doc_date else None,
        "tax_amount": str(gst).strip() if gst else None,
    }
    merchant = raw.get("merchant_name")
    if merchant is not None and str(merchant).strip():
        out["merchant_name"] = str(merchant).strip()
    for key in ("expense_category", "business_purpose"):
        val = raw.get(key)
        if val is not None and str(val).strip():
            out[key] = str(val).strip()
    gl_id = raw.get("gl_account_id")
    if gl_id is not None and str(gl_id).strip():
        out["gl_account_id"] = str(gl_id).strip()
    return out


def extracted_fields_to_invoice(fields: dict[str, Any]) -> ExtractedInvoice:
    norm = normalize_extracted_fields(fields)
    return ExtractedInvoice(
        invoice_number=norm.get("document_number"),
        invoice_date=_parse_date(norm.get("document_date")),
        due_date=_parse_date(norm.get("due_date")),
        vendor_name=norm.get("vendor_name"),
        customer_name=fields.get("customer_name"),
        total_amount=norm.get("total_amount"),
        tax_amount=norm.get("gst_amount"),
        currency=norm.get("currency") or "SGD",
        payment_terms=norm.get("payment_terms"),
        missing_fields=[],
        warnings=list(fields.get("warnings") or []),
    )


def invoice_to_confirmation_fields(inv: Any, *, document_type: str | None = None) -> dict[str, str | None]:
    base = invoice_extracted_fields(inv)
    base["document_type"] = document_type or "invoice"
    base["document_number"] = base.get("invoice_number")
    base["document_date"] = base.get("invoice_date")
    base["gst_amount"] = base.get("tax_amount")
    base["sender_validated"] = "false"
    return normalize_extracted_fields(base)


def expense_claim_to_confirmation_fields(claim: Any) -> dict[str, str | None]:
    return normalize_extracted_fields(
        {
            "document_type": "expense_claim",
            "vendor_name": claim.claimant_name,
            "total_amount": str(claim.total_claimed),
            "currency": claim.currency,
            "payment_terms": None,
            "document_number": claim.case_number,
            "document_date": str(claim.claim_period_from),
            "due_date": str(claim.claim_period_to),
            "gst_amount": None,
            "sender_validated": "false",
        }
    )


def expense_fields_to_confirmation(extracted: dict) -> dict[str, str | None]:
    """Expense claim fields for Finance UI parsing confirmation."""
    return normalize_extracted_fields(dict(extracted))


async def mailbox_for_case(
    session: AsyncSession, email: Email | None
) -> MailGatewayConfig | None:
    if email is None or not email.mailbox_address:
        return None
    svc = ExecutiveMailService(session)
    return await svc.get_mailbox_for_address(email.mailbox_address)


async def requires_parsing_confirmation(
    session: AsyncSession, case: Case, email: Email | None
) -> bool:
    mailbox = await mailbox_for_case(session, email)
    if mailbox is None:
        return False
    addr = mailbox.email_address.strip().lower()
    if addr not in PARSING_CONFIRMATION_EXECUTIVE_ADDRESSES:
        return False
    return bool(mailbox.require_parsing_confirmation)


async def send_parsing_confirmation_notifications(
    session: AsyncSession,
    *,
    case: Case,
    extracted_fields: dict[str, str | None],
) -> None:
    settings = get_settings()
    case_url = f"{settings.edge_public_base_url}/cases/{case.id}"
    doc_type = extracted_fields.get("document_type") or "document"
    vendor = extracted_fields.get("vendor_name") or case.counterparty_name or "Unknown"
    subject = (
        f"[{case.case_number}] Parsing confirmation required — "
        f"{doc_type} from {vendor}"
    )
    lines = [
        "Extracted fields (confirm or correct in Finance UI):",
        "",
    ]
    for key in sorted(extracted_fields.keys()):
        value = extracted_fields.get(key)
        if value is None or value == "":
            continue
        label = key.replace("_", " ").title()
        lines.append(f"  {label}: {value}")
    lines.extend(
        [
            "",
            f"Open case: {case_url}",
            "",
            "No email actions — review and confirm in the Finance UI.",
        ]
    )
    body_plain = "\n".join(lines)

    exec_svc = ExecutiveMailService(session)
    sender_mailbox = await exec_svc.get_mailbox_for_address(SENDER_MAILBOX)
    if sender_mailbox is None:
        return

    outbound = PendingOutboundEmail(
        case_id=case.id,
        email_id=case.email_id,
        mailbox_id=sender_mailbox.id,
        to_addresses=list(PARSING_CONFIRMATION_NOTIFY_TO),
        cc_addresses=[],
        subject=subject,
        body_plain=body_plain,
        message_type="other",
        status="approved",
        metadata_={
            "template": "parsing.confirmation.required",
            "case_number": case.case_number,
            "case_url": case_url,
        },
    )
    session.add(outbound)
    await session.flush()
    outbound_svc = OutboundMailService(session)
    email_row = None
    if case.email_id:
        result = await session.execute(select(Email).where(Email.id == case.email_id))
        email_row = result.scalar_one_or_none()
    await outbound_svc.try_send_pending(outbound, source_email=email_row)


async def pause_for_parsing_confirmation(
    session: AsyncSession,
    *,
    case: Case,
    email: Email | None,
    extracted_fields: dict[str, str | None],
    extraction_confidence: float,
    actor_name: str,
) -> dict:
    cases = CaseRepository(session)
    norm = normalize_extracted_fields(extracted_fields)
    from_status = case.status
    case.status = "pending_confirmation"
    meta = dict(case.workflow_metadata or {})
    meta.update(
        {
            "extracted_fields": norm,
            "extraction_confidence": extraction_confidence,
            "pending_parsing_confirmation": True,
            "current_stage": "parsing_confirmation",
        }
    )
    case.workflow_metadata = meta
    case.confidence_score = extraction_confidence

    await cases.add_timeline(
        case_id=case.id,
        event_type="parsing_awaiting_confirmation",
        from_status=from_status,
        to_status="pending_confirmation",
        actor=actor_name,
        description="Parsing complete — awaiting Finance UI confirmation",
        metadata={"extraction_confidence": extraction_confidence},
    )
    await send_parsing_confirmation_notifications(
        session, case=case, extracted_fields=norm
    )
    await session.flush()
    return {
        "status": "pending_confirmation",
        "case_id": str(case.id),
        "reason": "parsing_confirmation_required",
    }
