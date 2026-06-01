"""Ollama expense claim extraction — accexp mailbox pipeline."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from agents.hermes.llm_extract import _EXPENSE_CLAIM_PROMPT
from agents.hermes.ollama_client import EXTRACTION_MODEL, OllamaError, generate_json
from app.schemas.hermes import (
    ExtractExpenseClaimRequest,
    ExtractExpenseClaimResponse,
    ExtractedExpenseLineItem,
    ExtractExpenseClaimOutput,
)
from app.utils.expense_categories import normalize_expense_category
from app.utils.hermes_amounts import clean_decimal_amount_string

logger = logging.getLogger(__name__)


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


def _output_from_flat(data: dict, categories: list[str]) -> ExtractExpenseClaimOutput:
    line_items: list[ExtractedExpenseLineItem] = []
    for idx, row in enumerate(data.get("line_items") or [], start=1):
        if not isinstance(row, dict):
            continue
        category = normalize_expense_category(str(row.get("category") or "other"))
        line_items.append(
            ExtractedExpenseLineItem(
                line_number=int(row.get("line_number") or idx),
                expense_date=_parse_date(row.get("expense_date")),
                category=category,
                description=str(row.get("description") or ""),
                merchant=row.get("merchant"),
                currency=str(row.get("currency") or data.get("currency") or "SGD"),
                amount_claimed=clean_decimal_amount_string(row.get("amount_claimed")),
                confidence=float(row.get("confidence") or 0.0),
            )
        )

    if not line_items and data.get("total_amount"):
        category = normalize_expense_category(data.get("expense_category"))
        line_items.append(
            ExtractedExpenseLineItem(
                line_number=1,
                expense_date=_parse_date(data.get("document_date")),
                category=category,
                description=str(data.get("business_purpose") or data.get("purpose") or "Expense"),
                merchant=row.get("merchant") or data.get("vendor_name"),
                currency=str(data.get("currency") or "SGD"),
                amount_claimed=clean_decimal_amount_string(data.get("total_amount")),
                confidence=float(data.get("confidence_score") or 0.85),
            )
        )

    missing = [str(m) for m in (data.get("missing_fields") or [])]
    if not line_items and "line_items" not in missing:
        missing.append("line_items")

    return ExtractExpenseClaimOutput(
        confidence_score=float(data.get("confidence_score") or 0.85),
        claim_period_from=_parse_date(data.get("claim_period_from")),
        claim_period_to=_parse_date(data.get("claim_period_to")),
        purpose=data.get("business_purpose") or data.get("purpose"),
        currency=str(data.get("currency") or "SGD"),
        line_items=line_items,
        missing_fields=missing,
        warnings=[str(w) for w in (data.get("warnings") or [])],
    )


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
        "travel",
        "accommodation",
        "entertainment",
        "office_supplies",
        "government_fees",
        "other",
    ]
    hints_block = (request.vendor_hints or "").strip()
    if hints_block:
        hints_block = hints_block if hints_block.endswith("\n\n") else f"{hints_block}\n\n"
    prompt = hints_block + _EXPENSE_CLAIM_PROMPT.format(
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

    output = _output_from_flat(data, categories)
    return ExtractExpenseClaimResponse(
        success=True,
        confidence_score=output.confidence_score,
        model_used=EXTRACTION_MODEL,
        output=output,
    )
