"""Ollama expense claim extraction — accexp mailbox pipeline."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from agents.hermes.ollama_client import EXTRACTION_MODEL, OllamaError, generate_json
from app.schemas.hermes import (
    ExtractExpenseClaimRequest,
    ExtractExpenseClaimResponse,
    ExtractedExpenseLineItem,
    ExtractExpenseClaimOutput,
)

logger = logging.getLogger(__name__)

_EXPENSE_PROMPT = """You are an expense claim extractor for mmlogistix finance.
Extract expense claim line items from employee reimbursement invoices and receipts.
Documents sent to the accexp mailbox are employee expense claims (NOT supplier AP invoices).
If the document shows "Invoice No", "From:", employee name, and "Category:" (e.g. Home office expense reimbursement),
extract as expense claim line items — map the total to amount_claimed and category from the document.
Categories MUST be one of: meals, transport, accommodation, entertainment, other, office_supplies.

Return ONLY valid JSON:
{{
  "confidence_score": float,
  "claim_period_from": "YYYY-MM-DD"|null,
  "claim_period_to": "YYYY-MM-DD"|null,
  "purpose": string|null,
  "currency": string,
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

Claimant hint: {claimant_hint}
Department hint: {department_hint}
Allowed categories: {categories}

SOURCE TEXT:
{source_text}
"""


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _build_source_text(request: ExtractExpenseClaimRequest) -> str:
    parts: list[str] = []
    if request.email_body.strip():
        parts.append(f"Email body:\n{request.email_body.strip()}")
    for att in request.attachments:
        if not isinstance(att, dict):
            continue
        name = att.get("filename") or "attachment"
        text = att.get("extracted_text") or ""
        if text.strip():
            parts.append(f"Attachment {name}:\n{text.strip()}")
    return "\n\n".join(parts)


async def extract_expense_claim_llm(
    request: ExtractExpenseClaimRequest,
) -> ExtractExpenseClaimResponse:
    source_text = _build_source_text(request)
    if not source_text.strip():
        return ExtractExpenseClaimResponse(
            success=False,
            error_message="No email body or attachment text to extract",
            output=ExtractExpenseClaimOutput(
                missing_fields=["email_body", "attachments"],
            ),
        )

    categories = request.expense_categories or [
        "meals",
        "transport",
        "accommodation",
        "entertainment",
        "other",
    ]
    prompt = _EXPENSE_PROMPT.format(
        source_text=source_text[:12000],
        claimant_hint=request.claimant_hint or "unknown",
        department_hint=request.department_hint or "unknown",
        categories=", ".join(categories),
    )
    try:
        data = await generate_json(prompt=prompt, model=EXTRACTION_MODEL)
    except OllamaError as exc:
        logger.warning("Ollama expense extraction failed: %s", exc)
        return ExtractExpenseClaimResponse(success=False, error_message=str(exc))

    line_items: list[ExtractedExpenseLineItem] = []
    for idx, row in enumerate(data.get("line_items") or [], start=1):
        if not isinstance(row, dict):
            continue
        category = str(row.get("category") or "other").lower()
        if category not in categories:
            category = "other"
        line_items.append(
            ExtractedExpenseLineItem(
                line_number=int(row.get("line_number") or idx),
                expense_date=_parse_date(row.get("expense_date")),
                category=category,
                description=str(row.get("description") or ""),
                merchant=row.get("merchant"),
                currency=str(row.get("currency") or data.get("currency") or "SGD"),
                amount_claimed=str(row.get("amount_claimed") or "0"),
                confidence=float(row.get("confidence") or 0.0),
            )
        )

    missing = [str(m) for m in (data.get("missing_fields") or [])]
    if not line_items and "line_items" not in missing:
        missing.append("line_items")

    output = ExtractExpenseClaimOutput(
        confidence_score=float(data.get("confidence_score") or 0.85),
        claim_period_from=_parse_date(data.get("claim_period_from")),
        claim_period_to=_parse_date(data.get("claim_period_to")),
        purpose=data.get("purpose"),
        currency=str(data.get("currency") or "SGD"),
        line_items=line_items,
        missing_fields=missing,
        warnings=[str(w) for w in (data.get("warnings") or [])],
    )
    return ExtractExpenseClaimResponse(
        success=True,
        confidence_score=output.confidence_score,
        model_used=EXTRACTION_MODEL,
        output=output,
    )
