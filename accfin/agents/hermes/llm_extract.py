"""Ollama-powered structured extraction — `04` §6.2, §8.4."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from agents.hermes.extract import (
    extract_invoice_stub,
    extract_payment_advice_stub,
)
from agents.hermes.ollama_client import EXTRACTION_MODEL, OllamaError, generate_json
from app.constants.tenant import TENANT_MMLOGISTIX
from app.core.database import get_session_factory
from app.schemas.hermes import (
    ExtractInvoiceRequest,
    ExtractInvoiceResponse,
    ExtractPaymentAdviceRequest,
    ExtractPaymentAdviceResponse,
    ExtractedInvoice,
    ExtractedPaymentAdvice,
    InvoiceAllocation,
    InvoiceLineItem,
)
from app.services.vendor_extraction_hints import load_hints_prompt_block

logger = logging.getLogger(__name__)

_AP_INVOICE_PROMPT = """You are an AP invoice data extractor for mmlogistix finance.
Extract structured fields from the supplier invoice, receipt, or payment document text below.

VENDOR (vendor_name): The company or entity that ISSUED the invoice — the seller or service
provider. Do NOT use the buyer, payer, or customer name as vendor_name. Example: on an ACRA receipt,
vendor_name is "ACRA" or "Accounting and Corporate Regulatory Authority", NOT "MMLOGISTIX PTE LTD"
(the customer who paid).

INVOICE NUMBER (invoice_number): Accept values labelled Invoice no., Receipt no., Receipt number,
Reference no., Ref no., ARN, Document no., or similar.

INVOICE DATE (invoice_date): Accept Date and time, Date of service, Transaction date, Payment date,
Invoice date, or similar. Format as YYYY-MM-DD.

DUE DATE (due_date): Payment due date from payment terms when present. For receipts or documents
that are already paid (payment confirmed, receipt issued after payment), set due_date equal to
invoice_date.

Return ONLY valid JSON matching this schema:
{{
  "invoice_number": string|null,
  "invoice_date": "YYYY-MM-DD"|null,
  "due_date": "YYYY-MM-DD"|null,
  "payment_due_date": "YYYY-MM-DD"|null,
  "vendor_name": string|null,
  "po_reference": string|null,
  "subtotal": string|null,
  "tax_amount": string|null,
  "tax_code": string|null,
  "total_amount": string|null,
  "currency": string,
  "exchange_rate": string|null,
  "sgd_amount": string|null,
  "payment_terms": string|null,
  "line_items": [{{"description": string, "quantity": string|null, "unit_price": string|null, "amount": string|null}}],
  "missing_fields": [string],
  "warnings": [string],
  "confidence_score": float
}}
Use amounts as decimal strings without currency symbols. Currency default {currency_hint}.
If currency is SGD, set sgd_amount equal to total_amount; if foreign currency, extract exchange_rate
from the email body when the sender states a conversion (e.g. "1 USD = 1.35 SGD", "USD/SGD 1.35",
"exchange rate: 1.35", "conversion rate: 1.35") and leave sgd_amount null for worker calculation.
Do not copy the supplier hint as vendor_name unless the document confirms that entity issued the invoice.
Supplier hint (context only): {supplier_hint}

DOCUMENT TEXT:
{document_text}
"""

_AR_INVOICE_PROMPT = """You are an AR invoice data extractor for mmlogistix finance.
Extract customer invoice fields from the text below.
Always extract due_date (payment due date) when present in the document or derivable from payment terms.
Return ONLY valid JSON matching this schema:
{{
  "invoice_number": string|null,
  "invoice_date": "YYYY-MM-DD"|null,
  "due_date": "YYYY-MM-DD"|null,
  "payment_due_date": "YYYY-MM-DD"|null,
  "customer_name": string|null,
  "subtotal": string|null,
  "tax_amount": string|null,
  "tax_code": string|null,
  "total_amount": string|null,
  "currency": string,
  "payment_terms": string|null,
  "line_items": [{{"description": string, "quantity": string|null, "unit_price": string|null, "amount": string|null}}],
  "missing_fields": [string],
  "warnings": [string],
  "confidence_score": float
}}
Use amounts as decimal strings without currency symbols. Currency default {currency_hint}.
Customer hint: {customer_hint}

DOCUMENT TEXT:
{document_text}
"""

_PAYMENT_ADVICE_PROMPT = """Extract payment advice / remittance fields from the text below.
Return ONLY valid JSON:
{{
  "payer_name": string|null,
  "payment_date": "YYYY-MM-DD"|null,
  "payment_amount": string|null,
  "currency": string,
  "bank_reference": string|null,
  "allocations": [{{"invoice_number": string, "amount_applied": string, "discount_taken": "0.00"}}],
  "unallocated_amount": string,
  "missing_fields": [string],
  "warnings": [string],
  "confidence_score": float
}}
Currency default {currency_hint}. Customer hint: {customer_hint}.

DOCUMENT TEXT:
{document_text}
"""


_PAID_RECEIPT_RE = re.compile(
    r"\b("
    r"receipt|paid|payment\s+received|payment\s+confirmed|already\s+paid|"
    r"payment\s+successful|amount\s+paid|transaction\s+successful"
    r")\b",
    re.I,
)

_EXCHANGE_RATE_PATTERNS = (
    re.compile(r"1\s+([A-Z]{3})\s*=\s*([\d.]+)\s*SGD", re.I),
    re.compile(r"([A-Z]{3})/SGD\s+([\d.]+)", re.I),
    re.compile(r"exchange\s+rate\s*:?\s*([\d.]+)", re.I),
    re.compile(r"conversion\s+rate\s*:?\s*([\d.]+)", re.I),
)


def _normalize_ap_due_date(
    invoice_date: date | None,
    due_date: date | None,
    document_text: str,
) -> date | None:
    if due_date:
        return due_date
    if invoice_date and _PAID_RECEIPT_RE.search(document_text):
        return invoice_date
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_exchange_rate_from_text(document_text: str, currency: str) -> str | None:
    for pattern in _EXCHANGE_RATE_PATTERNS:
        match = pattern.search(document_text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 2:
            found_currency, rate = groups
            if found_currency.upper() != currency.upper():
                continue
            return _normalize_amount(rate)
        if len(groups) == 1:
            return _normalize_amount(groups[0])
    return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _normalize_amount(value: Any) -> str | None:
    if value is None or value == "":
        return None
    cleaned = str(value).replace(",", "").replace("$", "").strip()
    try:
        return str(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        return str(value)


def _line_items(raw: Any) -> list[InvoiceLineItem]:
    if not isinstance(raw, list):
        return []
    items: list[InvoiceLineItem] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        items.append(
            InvoiceLineItem(
                description=str(row.get("description") or ""),
                quantity=_normalize_amount(row.get("quantity")),
                unit_price=_normalize_amount(row.get("unit_price")),
                amount=_normalize_amount(row.get("amount")),
            )
        )
    return items


def _invoice_missing_fields(extracted: ExtractedInvoice, *, role: str) -> list[str]:
    missing = list(extracted.missing_fields)
    required = ["invoice_number", "total_amount", "invoice_date", "due_date"]
    if role == "ap":
        required.append("vendor_name")
    else:
        required.append("customer_name")
    for field in required:
        if getattr(extracted, field, None) in (None, ""):
            if field not in missing:
                missing.append(field)
    return missing


def _build_document_text(request: ExtractInvoiceRequest) -> str:
    parts: list[str] = []
    if request.email_body.strip():
        parts.append(request.email_body.strip())
    if request.extracted_text.strip():
        parts.append(request.extracted_text.strip())
    return "\n\n".join(parts)


async def _vendor_hints_block(request: ExtractInvoiceRequest) -> str:
    vendor = (request.vendor_name_for_hints or request.supplier_hint or "").strip()
    if not vendor:
        return ""
    tenant_id = request.tenant_id or TENANT_MMLOGISTIX
    try:
        factory = get_session_factory()
        async with factory() as session:
            return await load_hints_prompt_block(
                session, tenant_id=tenant_id, vendor_name=vendor
            )
    except Exception:
        logger.warning("Could not load vendor extraction hints for %s", vendor, exc_info=True)
        return ""


async def extract_invoice_llm(request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
    document_text = _build_document_text(request)
    if not document_text.strip():
        return extract_invoice_stub(request)

    role = (request.document_role or "ap").lower()
    template = _AR_INVOICE_PROMPT if role == "ar" else _AP_INVOICE_PROMPT
    hints_block = await _vendor_hints_block(request) if role == "ap" else ""
    prompt = hints_block + template.format(
        document_text=document_text[:12000],
        currency_hint=request.currency_hint or "SGD",
        supplier_hint=request.supplier_hint or "unknown",
        customer_hint=request.customer_hint or request.supplier_hint or "unknown",
    )
    try:
        data = await generate_json(prompt=prompt, model=EXTRACTION_MODEL)
    except OllamaError as exc:
        logger.warning("Ollama invoice extraction failed, using stub: %s", exc)
        return extract_invoice_stub(request)

    line_items = _line_items(data.get("line_items"))
    invoice_date = _parse_date(data.get("invoice_date"))
    due_date = _parse_date(data.get("due_date") or data.get("payment_due_date"))
    if role == "ap":
        due_date = _normalize_ap_due_date(invoice_date, due_date, document_text)
    vendor_name = _optional_str(data.get("vendor_name"))
    customer_name = _optional_str(data.get("customer_name"))
    if role != "ap":
        vendor_name = vendor_name or request.supplier_hint
        customer_name = customer_name or request.customer_hint
    currency = str(data.get("currency") or request.currency_hint or "SGD").strip().upper()
    total_amount = _normalize_amount(data.get("total_amount"))
    exchange_rate = _normalize_amount(data.get("exchange_rate"))
    sgd_amount = _normalize_amount(data.get("sgd_amount"))
    if role == "ap":
        if not exchange_rate and currency != "SGD":
            exchange_rate = _extract_exchange_rate_from_text(document_text, currency)
        if currency == "SGD" and total_amount:
            sgd_amount = total_amount
        elif currency != "SGD":
            sgd_amount = None
    extracted = ExtractedInvoice(
        invoice_number=_optional_str(data.get("invoice_number")),
        invoice_date=invoice_date,
        due_date=due_date,
        vendor_name=vendor_name,
        customer_name=customer_name,
        po_reference=data.get("po_reference"),
        subtotal=_normalize_amount(data.get("subtotal")),
        tax_amount=_normalize_amount(data.get("tax_amount")),
        tax_code=_optional_str(data.get("tax_code")),
        total_amount=total_amount,
        currency=currency,
        exchange_rate=exchange_rate,
        sgd_amount=sgd_amount,
        payment_terms=data.get("payment_terms"),
        line_items=line_items,
        warnings=[str(w) for w in (data.get("warnings") or [])],
    )
    extracted.missing_fields = _invoice_missing_fields(extracted, role=role)
    confidence = float(data.get("confidence_score") or 0.85)
    if extracted.missing_fields:
        confidence = min(confidence, 0.75)
    return ExtractInvoiceResponse(
        confidence_score=round(confidence, 2),
        model_used=EXTRACTION_MODEL,
        prompt_version="ar_invoice_extract-v1" if role == "ar" else "ap_invoice_extract-v3",
        output=extracted,
    )


async def extract_payment_advice_llm(
    request: ExtractPaymentAdviceRequest,
) -> ExtractPaymentAdviceResponse:
    document_text = (request.extracted_text or "").strip()
    if not document_text:
        return extract_payment_advice_stub(request)

    prompt = _PAYMENT_ADVICE_PROMPT.format(
        document_text=document_text[:12000],
        currency_hint=request.currency_hint or "SGD",
        customer_hint=request.customer_hint or "unknown",
    )
    try:
        data = await generate_json(prompt=prompt, model=EXTRACTION_MODEL)
    except OllamaError as exc:
        logger.warning("Ollama payment advice extraction failed, using stub: %s", exc)
        return extract_payment_advice_stub(request)

    allocations: list[InvoiceAllocation] = []
    for row in data.get("allocations") or []:
        if not isinstance(row, dict) or not row.get("invoice_number"):
            continue
        allocations.append(
            InvoiceAllocation(
                invoice_number=str(row["invoice_number"]),
                amount_applied=_normalize_amount(row.get("amount_applied")) or "0",
                discount_taken=_normalize_amount(row.get("discount_taken")) or "0.00",
            )
        )
    missing = [str(m) for m in (data.get("missing_fields") or [])]
    if not data.get("payment_amount") and "payment_amount" not in missing:
        missing.append("payment_amount")

    extracted = ExtractedPaymentAdvice(
        payer_name=data.get("payer_name") or request.customer_hint,
        payment_date=_parse_date(data.get("payment_date")),
        payment_amount=_normalize_amount(data.get("payment_amount")),
        currency=str(data.get("currency") or request.currency_hint or "SGD"),
        bank_reference=data.get("bank_reference"),
        allocations=allocations,
        unallocated_amount=_normalize_amount(data.get("unallocated_amount")) or "0.00",
        missing_fields=missing,
        warnings=[str(w) for w in (data.get("warnings") or [])],
    )
    confidence = float(data.get("confidence_score") or 0.85)
    return ExtractPaymentAdviceResponse(
        confidence_score=round(confidence, 2),
        model_used=EXTRACTION_MODEL,
        output=extracted,
    )


# Expense claim extraction — accexp mailbox (`0.14.45-expense-workflow`).
# Used by agents.hermes.expense_extract.extract_expense_claim_llm.
_EXPENSE_CLAIM_PROMPT = """You are an expense claim extractor for mmlogistix finance.
Extract fields from employee reimbursement receipts, invoices, and credit card statements.
Documents sent to the accexp mailbox are employee expense claims (NOT supplier AP invoices).

Return ONLY valid JSON:
{{
  "confidence_score": float,
  "document_type": "receipt"|"invoice"|"credit_card_statement",
  "document_date": "YYYY-MM-DD"|null,
  "document_number": string|null,
  "merchant_name": string,
  "total_amount": string,
  "currency": string,
  "gst_amount": string|null,
  "expense_category": "meals"|"travel"|"accommodation"|"office_supplies"|"government_fees"|"entertainment"|"other",
  "business_purpose": string,
  "exchange_rate": string|null,
  "claim_period_from": "YYYY-MM-DD"|null,
  "claim_period_to": "YYYY-MM-DD"|null,
  "purpose": string|null,
  "line_items": [
    {{
      "line_number": int,
      "expense_date": "YYYY-MM-DD"|null,
      "category": string,
      "description": string,
      "merchant": string|null,
      "currency": string,
      "amount_claimed": string,
      "confidence": float
    }}
  ],
  "missing_fields": [string],
  "warnings": [string]
}}

expense_category MUST be one of: meals, travel, accommodation, office_supplies, government_fees, entertainment, other.
Map transport/taxi to travel. merchant_name is the vendor who issued the receipt (not the employee).

Claimant hint: {claimant_hint}
Department hint: {department_hint}
Allowed categories: {categories}

SOURCE TEXT:
{source_text}
"""
