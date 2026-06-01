"""Re-run Hermes extraction with vendor hints — updates extracted_fields in place."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.clients.hermes import HermesClient, HermesError
from app.constants.tenant import TENANT_MMLOGISTIX
from app.core.database import get_session_factory
from app.core.exceptions import AppHTTPException
from app.models.case import Case
from app.models.mail import Email, EmailAttachment
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.schemas.case_re_extract import ReExtractResponse
from app.schemas.hermes import ExtractExpenseClaimRequest, ExtractInvoiceRequest
from app.services.email_context import build_extraction_context, ensure_attachment_texts
from app.services.vendor_extraction_hints import (
    format_vendor_hints_prompt,
    get_hints_for_vendor,
)
from app.utils.expense_categories import normalize_expense_category
from app.utils.hermes_amounts import clean_decimal_amount_string, decimal_from_hermes_amount
from fastapi import status
from workers.common.ap_validation import extract_sender_validation
from workers.common.expense_validation import expense_extraction_to_fields
from workers.common.missing_fields_escalation import invoice_extracted_fields
from workers.common.parsing_confirmation import (
    expense_fields_to_confirmation,
    invoice_to_confirmation_fields,
    normalize_extracted_fields,
)

_EXPENSE_CATEGORIES = (
    "meals",
    "travel",
    "accommodation",
    "entertainment",
    "office_supplies",
    "government_fees",
    "other",
)


def _vendor_name_for_hints(case: Case) -> str | None:
    meta = case.workflow_metadata or {}
    extracted = meta.get("extracted_fields")
    if isinstance(extracted, dict):
        raw = extracted.get("vendor_name") or extracted.get("merchant_name")
        if raw:
            name = str(raw).strip()
            if name:
                return name
    if case.counterparty_name:
        name = case.counterparty_name.strip()
        if name:
            return name
    return None


async def _vendor_hints_block(session: AsyncSession, vendor_name: str | None) -> str | None:
    if not vendor_name:
        return None
    hints = await get_hints_for_vendor(
        session, vendor_name, tenant_id=TENANT_MMLOGISTIX
    )
    block = format_vendor_hints_prompt(hints, vendor_name=vendor_name)
    return block or None


async def _email_for_case(session: AsyncSession, case: Case) -> Email | None:
    if not case.email_id:
        return None
    result = await session.execute(select(Email).where(Email.id == case.email_id))
    return result.scalar_one_or_none()


async def _re_extract_expense(
    session: AsyncSession,
    case: Case,
    email: Email | None,
    *,
    hermes: HermesClient,
) -> tuple[dict[str, str | None], float]:
    body = ""
    attachments: list[dict] = []
    vendor_name = _vendor_name_for_hints(case)
    vendor_hints = await _vendor_hints_block(session, vendor_name)
    if email:
        body = email.body_text or email.body_preview or ""
        await ensure_attachment_texts(session, email.id, hermes=hermes)
        result = await session.execute(
            select(EmailAttachment).where(EmailAttachment.email_id == email.id).limit(5)
        )
        for att in result.scalars().all():
            attachments.append(
                {
                    "attachment_id": str(att.id),
                    "filename": att.filename,
                    "extracted_text": att.extracted_text or "",
                }
            )
    try:
        out = await hermes.extract_expense_claim(
            ExtractExpenseClaimRequest(
                email_id=str(case.email_id or case.id),
                email_body=body,
                attachments=attachments,
                vendor_hints=vendor_hints,
                expense_categories=list(_EXPENSE_CATEGORIES),
            )
        )
    except HermesError as exc:
        raise AppHTTPException(
            status.HTTP_502_BAD_GATEWAY,
            exc.error_code or "HERMES_ERROR",
            str(exc),
        ) from exc

    if not out.line_items:
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "EXTRACTION_EMPTY",
            "Hermes returned no line items",
        )

    flat = {
        "document_type": "receipt",
        "document_date": str(out.line_items[0].expense_date or out.claim_period_to or ""),
        "document_number": None,
        "vendor_name": out.line_items[0].merchant,
        "total_amount": clean_decimal_amount_string(out.line_items[0].amount_claimed),
        "currency": out.currency,
        "expense_category": out.line_items[0].category,
        "business_purpose": out.purpose,
        "tax_amount": None,
    }
    total = sum(decimal_from_hermes_amount(li.amount_claimed) for li in out.line_items)
    flat["total_amount"] = str(total)
    sender_val = extract_sender_validation(
        email.subject if email else None,
        email.body_text if email else None,
    )
    fields = expense_extraction_to_fields(flat, sender_val=sender_val)
    fields["expense_category"] = normalize_expense_category(flat.get("expense_category"))
    confidence = float(out.confidence_score or 0.85)
    return expense_fields_to_confirmation(fields), confidence


async def _re_extract_invoice(
    session: AsyncSession,
    case: Case,
    email: Email | None,
    *,
    hermes: HermesClient,
    document_role: str,
) -> tuple[dict[str, str | None], float]:
    if not case.email_id:
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "NO_EMAIL",
            "Case has no linked email for re-extraction",
        )
    text, att_id, body = await build_extraction_context(
        session, case.email_id, hermes=hermes
    )
    vendor_for_hints = _vendor_name_for_hints(case)
    try:
        extraction = await hermes.extract_invoice(
            ExtractInvoiceRequest(
                case_id=case.id,
                attachment_id=att_id or case.id,
                extracted_text=text,
                email_body=body,
                document_role=document_role,
                supplier_hint=case.counterparty_name,
                currency_hint=case.amount_currency or "SGD",
                tenant_id=TENANT_MMLOGISTIX,
                vendor_name_for_hints=vendor_for_hints,
            )
        )
    except HermesError as exc:
        raise AppHTTPException(
            status.HTTP_502_BAD_GATEWAY,
            exc.error_code or "HERMES_ERROR",
            str(exc),
        ) from exc

    inv = extraction.output
    if inv is None:
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "EXTRACTION_EMPTY",
            "Hermes returned no invoice output",
        )

    extracted = invoice_extracted_fields(inv)
    extracted["document_type"] = getattr(inv, "document_type", None) or (
        "invoice" if document_role == "ap" else "ar_invoice"
    )
    confirm_fields = invoice_to_confirmation_fields(
        inv, document_type=extracted.get("document_type")
    )
    if email:
        sender_val = extract_sender_validation(email.subject, email.body_text)
        confirm_fields["sender_validated"] = (
            "true" if sender_val.get("sender_validated") else "false"
        )
    confidence = float(extraction.confidence_score or 0.0)
    return confirm_fields, confidence


async def execute_case_re_extract(
    case_id: UUID,
    *,
    user: TokenData,
) -> ReExtractResponse:
    del user  # permission enforced on route
    factory = get_session_factory()
    hermes = HermesClient()
    async with factory() as session:
        cases = CaseRepository(session)
        case = await cases.get(case_id)
        if case is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found"
            )
        if case.status != "pending_confirmation":
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_STATUS",
                f"Case must be pending_confirmation (current: {case.status})",
            )

        email = await _email_for_case(session, case)
        case_type = (case.type or "").strip()

        if case_type == "expense_claim":
            fields, confidence = await _re_extract_expense(
                session, case, email, hermes=hermes
            )
        elif case_type == "ap_invoice":
            fields, confidence = await _re_extract_invoice(
                session, case, email, hermes=hermes, document_role="ap"
            )
        elif case_type == "ar_invoice":
            fields, confidence = await _re_extract_invoice(
                session, case, email, hermes=hermes, document_role="ar"
            )
        else:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "UNSUPPORTED_CASE_TYPE",
                f"Re-extract is not supported for case type {case_type!r}",
            )

        normalized = normalize_extracted_fields(fields)
        meta = dict(case.workflow_metadata or {})
        meta["extracted_fields"] = normalized
        meta["extraction_confidence"] = confidence
        case.workflow_metadata = meta
        flag_modified(case, "workflow_metadata")
        await session.commit()

        return ReExtractResponse(
            case_id=case.id,
            case_number=case.case_number,
            status=case.status,
            extracted_fields=normalized,
            extraction_confidence=confidence,
        )
