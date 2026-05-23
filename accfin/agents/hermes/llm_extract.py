"""Ollama-powered structured extraction — `04` §6.2, §8.4."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from agents.hermes.extract import (
    extract_invoice_stub,
    extract_payment_advice_stub,
)
from agents.hermes.ollama_client import EXTRACTION_MODEL, OllamaError, generate_json
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

logger = logging.getLogger(__name__)

_AP_INVOICE_PROMPT = """You are an AP invoice data extractor for mmlogistix finance.
Extract structured fields from the supplier invoice text below.
Return ONLY valid JSON matching this schema:
{{
  "invoice_number": string|null,
  "invoice_date": "YYYY-MM-DD"|null,
  "due_date": "YYYY-MM-DD"|null,
  "vendor_name": string|null,
  "po_reference": string|null,
  "subtotal": string|null,
  "tax_amount": string|null,
  "total_amount": string|null,
  "currency": string,
  "payment_terms": string|null,
  "line_items": [{{"description": string, "quantity": string|null, "unit_price": string|null, "amount": string|null}}],
  "missing_fields": [string],
  "warnings": [string],
  "confidence_score": float
}}
Use amounts as decimal strings without currency symbols. Currency default {currency_hint}.
Supplier hint: {supplier_hint}

DOCUMENT TEXT:
{document_text}
"""

_AR_INVOICE_PROMPT = """You are an AR invoice data extractor for mmlogistix finance.
Extract customer invoice fields from the text below.
Return ONLY valid JSON matching this schema:
{{
  "invoice_number": string|null,
  "invoice_date": "YYYY-MM-DD"|null,
  "due_date": "YYYY-MM-DD"|null,
  "customer_name": string|null,
  "subtotal": string|null,
  "tax_amount": string|null,
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
    required = ["invoice_number", "total_amount", "invoice_date"]
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


async def extract_invoice_llm(request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
    document_text = _build_document_text(request)
    if not document_text.strip():
        return extract_invoice_stub(request)

    role = (request.document_role or "ap").lower()
    template = _AR_INVOICE_PROMPT if role == "ar" else _AP_INVOICE_PROMPT
    prompt = template.format(
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
    extracted = ExtractedInvoice(
        invoice_number=data.get("invoice_number"),
        invoice_date=_parse_date(data.get("invoice_date")),
        due_date=_parse_date(data.get("due_date")),
        vendor_name=data.get("vendor_name") or request.supplier_hint,
        customer_name=data.get("customer_name") or request.customer_hint,
        po_reference=data.get("po_reference"),
        subtotal=_normalize_amount(data.get("subtotal")),
        tax_amount=_normalize_amount(data.get("tax_amount")),
        total_amount=_normalize_amount(data.get("total_amount")),
        currency=str(data.get("currency") or request.currency_hint or "SGD"),
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
        prompt_version="ar_invoice_extract-v1" if role == "ar" else "ap_invoice_extract-v1",
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
