"""AR extraction completeness and risk flags — `17` §4.4–4.5."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.hermes import ExtractedInvoice, ExtractedPaymentAdvice

CRITICAL_FIELDS: dict[str, frozenset[str]] = {
    "ar_invoice": frozenset({"document_number", "total_amount", "document_date", "currency"}),
    "ar_credit_note": frozenset(
        {"credit_note_number", "total_amount", "original_invoice_reference"}
    ),
    "ar_payment_advice": frozenset({"payment_amount", "currency", "payment_date"}),
}


def map_credit_note_fields(extracted: ExtractedInvoice) -> list[str]:
    """Treat document_number as credit_note_number for critical-field checks."""
    missing = list(extracted.missing_fields)
    if not extracted.document_number and "credit_note_number" not in missing:
        missing.append("credit_note_number")
    return missing


def has_critical_missing(case_type: str, missing_fields: list[str]) -> bool:
    critical = CRITICAL_FIELDS.get(case_type, frozenset())
    return bool(critical.intersection(missing_fields))


def compute_invoice_risk_flags(
    *,
    duplicate_score: float,
    amount: Decimal | None,
    warnings: list[str],
) -> list[str]:
    flags: list[str] = []
    if duplicate_score > 0.85:
        flags.append("duplicate_suspected")
    if "total_mismatch" in warnings:
        flags.append("amount_anomaly")
    if amount and amount > Decimal("50000"):
        flags.append("high_value_transaction")
    elif amount and amount > Decimal("10000"):
        flags.append("above_threshold")
    return flags


def compute_payment_risk_flags(
    *,
    unallocated: Decimal,
    invoice_not_found: bool,
    tolerance: Decimal = Decimal("1.00"),
) -> list[str]:
    flags: list[str] = []
    if unallocated > tolerance:
        flags.append("unallocated_amount")
    if invoice_not_found:
        flags.append("invoice_not_found")
    return flags


def evaluate_extraction_path(
    *,
    case_type: str,
    confidence: float,
    missing_fields: list[str],
    stp_eligible: bool,
    risk_flags: list[str],
) -> str:
    """Returns: posted | pending_approval | manual_review."""
    if has_critical_missing(case_type, missing_fields) or confidence < 0.70:
        return "manual_review"
    if stp_eligible and not risk_flags and confidence >= 0.90:
        return "posted"
    return "pending_approval"
