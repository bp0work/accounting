"""Expense claim workflow validation — Expense Process document steps 2A–2G."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, Counterparty
from app.models.expense import ExpensePolicy
from workers.common.ap_validation import extract_sender_validation, resolve_ap_sgd_amount

EXPENSE_DOCUMENT_TYPES = frozenset(
    {"receipt", "invoice", "credit_card_statement", "expense_claim"}
)
EXPENSE_CATEGORIES = frozenset(
    {
        "meals",
        "travel",
        "transport",
        "accommodation",
        "office_supplies",
        "government_fees",
        "entertainment",
        "other",
    }
)

# Preferred GL codes by category (tenant may configure accounts with these codes).
CATEGORY_EXPENSE_ACCOUNT_CODES: dict[str, str] = {
    "meals": "5100",
    "entertainment": "5100",
    "travel": "5200",
    "transport": "5200",
    "accommodation": "5300",
    "office_supplies": "5400",
    "government_fees": "5500",
    "other": "5590",
}

CATEGORY_POLICY_NAME: dict[str, str] = {
    "meals": "meal_daily_limit",
    "transport": "transport_trip_limit",
    "travel": "transport_trip_limit",
    "accommodation": "accommodation_nightly_limit",
    "entertainment": "entertainment_occasion_limit",
}

PARSING_MANDATORY_FIELDS = (
    "document_type",
    "document_date",
    "merchant_name",
    "total_amount",
    "currency",
    "expense_category",
)

PARSING_OPTIONAL_FIELDS = ("business_purpose",)


def normalize_expense_category(raw: str | None) -> str:
    if not raw:
        return "other"
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if key == "transport":
        return "travel"
    if key in EXPENSE_CATEGORIES:
        return key
    return "other"


def expense_parsing_missing(extracted: dict) -> list[str]:
    missing: list[str] = []
    for field in PARSING_MANDATORY_FIELDS:
        val = extracted.get(field)
        if val is None or str(val).strip() == "":
            missing.append(field)
    doc_type = str(extracted.get("document_type") or "").strip().lower()
    if doc_type and doc_type not in EXPENSE_DOCUMENT_TYPES:
        missing.append("document_type")
    return missing


def parse_document_date(extracted: dict) -> date | None:
    raw = extracted.get("document_date") or extracted.get("invoice_date")
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


async def check_expense_duplicate(
    session: AsyncSession,
    *,
    merchant_name: str,
    document_number: str | None,
    total_amount: Decimal | None,
    document_date: date | None,
    exclude_case_id: UUID | None = None,
    days: int = 90,
) -> tuple[bool, str | None]:
    """Match expense_claim cases on merchant + doc# + amount + date within window."""
    if not merchant_name.strip():
        return False, None
    cutoff = datetime.now(UTC) - timedelta(days=days)
    q = (
        select(Case)
        .where(
            Case.type == "expense_claim",
            Case.created_at >= cutoff,
        )
        .order_by(Case.created_at.desc())
        .limit(100)
    )
    if exclude_case_id:
        q = q.where(Case.id != exclude_case_id)
    result = await session.execute(q)
    doc_norm = (document_number or "").strip().lower()
    for existing in result.scalars().all():
        meta = existing.workflow_metadata or {}
        ext = meta.get("extracted_fields") or {}
        merchant = str(ext.get("merchant_name") or ext.get("vendor_name") or "").strip()
        if not merchant or merchant.lower() not in merchant_name.lower():
            if merchant_name.lower() not in merchant.lower():
                continue
        existing_doc = str(ext.get("document_number") or "").strip().lower()
        if doc_norm and existing_doc and existing_doc != doc_norm:
            continue
        if total_amount is not None and existing.amount_value is not None:
            if abs(float(existing.amount_value) - float(total_amount)) > 0.01:
                continue
        if document_date is not None:
            existing_date = parse_document_date(ext)
            if existing_date and existing_date != document_date:
                continue
        return True, existing.case_number
    return False, None


async def lookup_staff_by_email(
    session: AsyncSession, email_address: str
) -> tuple[Counterparty | None, str]:
    """Match staff counterparty on contact_email. Status: active | inactive | not_found."""
    addr = email_address.strip().lower()
    if not addr:
        return None, "not_found"
    result = await session.execute(
        select(Counterparty)
        .where(
            Counterparty.type == "staff",
            Counterparty.contact_email.isnot(None),
        )
        .order_by(Counterparty.name.asc())
    )
    for row in result.scalars().all():
        cp_email = (row.contact_email or "").strip().lower()
        if cp_email == addr:
            meta = row.extra_metadata or {}
            if meta.get("is_active") is False or meta.get("staff_status") == "inactive":
                return row, "inactive"
            return row, "active"
    return None, "not_found"


def check_expense_policy(
    *,
    extracted: dict,
    policies: list[ExpensePolicy],
    submission_date: date,
) -> tuple[bool, str | None, Decimal | None]:
    """Return (within_policy, category_label, limit_amount)."""
    category = normalize_expense_category(extracted.get("expense_category"))
    try:
        amount = Decimal(str(extracted.get("sgd_amount") or extracted.get("total_amount") or "0"))
    except (InvalidOperation, ValueError):
        amount = Decimal("0")

    policy_name = CATEGORY_POLICY_NAME.get(category)
    limit: Decimal | None = None
    for policy in policies:
        if not policy.is_active:
            continue
        if policy_name and policy.name != policy_name:
            continue
        if policy.category and policy.category != category:
            continue
        if policy.daily_limit and amount > policy.daily_limit:
            return False, category, policy.daily_limit
        if policy.per_claim_limit and amount > policy.per_claim_limit:
            return False, category, policy.per_claim_limit

    if (submission_date - (parse_document_date(extracted) or submission_date)).days > 365:
        return False, category, None

    return True, category, limit


def receipt_validity_issues(extracted: dict, *, today: date | None = None) -> list[str]:
    """Step 2E checks."""
    issues: list[str] = []
    ref = today or date.today()
    doc_date = parse_document_date(extracted)
    if doc_date is None:
        issues.append("document_date_missing")
    elif (ref - doc_date).days > 90:
        issues.append("receipt_older_than_90_days")
    try:
        total = Decimal(str(extracted.get("total_amount") or "0"))
        if total <= 0:
            issues.append("invalid_amount")
    except (InvalidOperation, ValueError):
        issues.append("invalid_amount")
    merchant = str(extracted.get("merchant_name") or "").strip()
    if not merchant:
        issues.append("merchant_missing")
    return issues


def resolve_expense_sgd_amount(extracted: dict) -> tuple[Decimal, dict, bool]:
    """Foreign currency conversion — same shape as AP ``resolve_ap_sgd_amount``."""
    fields = dict(extracted)
    fields.setdefault("total_amount", fields.get("total_amount"))
    return resolve_ap_sgd_amount(fields)


def expense_account_code_for_category(category: str) -> str:
    return CATEGORY_EXPENSE_ACCOUNT_CODES.get(
        normalize_expense_category(category), CATEGORY_EXPENSE_ACCOUNT_CODES["other"]
    )


def expense_extraction_to_fields(
    data: dict,
    *,
    sender_val: dict | None = None,
) -> dict[str, str | None]:
    """Map Hermes JSON / confirmed fields to workflow extracted_fields."""
    category = normalize_expense_category(data.get("expense_category"))
    sender = sender_val or {}
    validated = sender.get("sender_validated", False)
    return {
        "document_type": str(data.get("document_type") or "receipt"),
        "document_number": str(data.get("document_number")).strip()
        if data.get("document_number")
        else None,
        "document_date": str(data.get("document_date") or "")[:10] or None,
        "merchant_name": str(data.get("merchant_name") or "").strip() or None,
        "vendor_name": str(data.get("merchant_name") or "").strip() or None,
        "total_amount": str(data.get("total_amount") or "").strip() or None,
        "gst_amount": str(data.get("gst_amount") or "").strip() if data.get("gst_amount") else None,
        "currency": str(data.get("currency") or "SGD"),
        "exchange_rate": str(data.get("exchange_rate")).strip()
        if data.get("exchange_rate")
        else None,
        "expense_category": category,
        "business_purpose": str(data.get("business_purpose") or data.get("purpose") or "").strip()
        or None,
        "sender_validated": "true" if validated else "false",
        "sgd_amount": str(data.get("sgd_amount") or data.get("total_amount") or ""),
    }
