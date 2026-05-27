"""AP extraction completeness, PO risk, expense account — `17` §5."""

from __future__ import annotations

from decimal import Decimal

CRITICAL_FIELDS: dict[str, frozenset[str]] = {
    # AP Process document Step 1 mandatory fields
    "ap_invoice": frozenset(
        {
            "vendor_name",
            "invoice_number",   # document_number
            "total_amount",
            "invoice_date",     # document_date
            "due_date",
            "payment_terms",
            # document_type defaults to "invoice" when absent — not treated as missing
        }
    ),
    "ap_po_validation": frozenset({"po_reference", "total_amount", "vendor_name"}),
    "ap_payment_proposal": frozenset({"payment_amount", "currency"}),
}

DEFAULT_EXPENSE_ACCOUNT = "5500"


def has_critical_missing(case_type: str, missing_fields: list[str]) -> bool:
    critical = CRITICAL_FIELDS.get(case_type, frozenset())
    return bool(critical.intersection(missing_fields))


def resolve_expense_account_code(line_items: list | None) -> str:
    """Pick GL code from first line item account_code, else operating expense default."""
    if not line_items:
        return DEFAULT_EXPENSE_ACCOUNT
    for item in line_items:
        if isinstance(item, dict):
            code = item.get("account_code") or item.get("gl_code")
            if code:
                return str(code)
    return DEFAULT_EXPENSE_ACCOUNT


def compute_ap_invoice_risk_flags(
    *,
    duplicate_score: float,
    amount: Decimal | None,
    po_not_found: bool,
    po_mismatch: bool,
    warnings: list[str],
) -> list[str]:
    flags: list[str] = []
    if duplicate_score > 0.85:
        flags.append("duplicate_suspected")
    if po_not_found:
        flags.append("po_not_found")
    if po_mismatch:
        flags.append("po_amount_mismatch")
    if "total_mismatch" in warnings:
        flags.append("amount_anomaly")
    if amount and amount > Decimal("50000"):
        flags.append("high_value_transaction")
    elif amount and amount > Decimal("10000"):
        flags.append("above_threshold")
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
