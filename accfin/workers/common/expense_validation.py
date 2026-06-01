"""Expense claim workflow validation — Expense Process document steps 2A–2G."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, Counterparty
from app.models.expense import ExpensePolicy
from app.utils.expense_categories import (
    CATEGORY_EXPENSE_ACCOUNT_CODES,
    normalize_expense_category,
)
from app.utils.hermes_amounts import decimal_from_hermes_amount
from workers.common.ap_validation import extract_sender_validation, resolve_ap_sgd_amount

EXPENSE_DOCUMENT_TYPES = frozenset(
    {"receipt", "invoice", "credit_card_statement", "expense_claim"}
)

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
    "vendor_name",
    "total_amount",
    "currency",
)

PARSING_OPTIONAL_FIELDS = ("business_purpose",)


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
    raw = extracted.get("document_date")
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
    vendor_name: str,
    document_number: str | None,
    total_amount: Decimal | None,
    document_date: date | None,
    exclude_case_id: UUID | None = None,
    days: int = 90,
) -> tuple[bool, str | None]:
    """Match expense_claim cases on vendor + doc# + amount + date within window."""
    if not vendor_name.strip():
        return False, None
    cutoff = datetime.now(UTC) - timedelta(days=days)
    q = (
        select(Case)
        .where(
            Case.type == "expense_claim",
            Case.created_at >= cutoff,
            Case.status.notin_(["rejected", "case_rejected", "case_closed"]),
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
        vendor = str(ext.get("vendor_name") or "").strip()
        if not vendor or vendor.lower() not in vendor_name.lower():
            if vendor_name.lower() not in vendor.lower():
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
            Counterparty.type == "employee",
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
        amount = decimal_from_hermes_amount(
            extracted.get("sgd_amount") or extracted.get("total_amount")
        )
    except (InvalidOperation, ValueError):
        amount = Decimal("0")

    policy_name = CATEGORY_POLICY_NAME.get(category)
    limit: Decimal | None = None

    if policy_name is None:
        if (submission_date - (parse_document_date(extracted) or submission_date)).days > 548:
            return False, category, None
        return True, category, None

    for policy in policies:
        if not policy.is_active:
            continue
        if policy.name != policy_name:
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
        total = decimal_from_hermes_amount(extracted.get("total_amount"))
        if total <= 0:
            issues.append("invalid_amount")
    except (InvalidOperation, ValueError):
        issues.append("invalid_amount")
    vendor = str(extracted.get("vendor_name") or "").strip()
    if not vendor:
        issues.append("vendor_missing")
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
    sender = sender_val or {}
    validated = sender.get("sender_validated", False)
    vendor = str(data.get("vendor_name") or data.get("merchant_name") or "").strip() or None
    tax = data.get("tax_amount")
    if tax is None:
        tax = data.get("gst_amount")
    return {
        "document_type": str(data.get("document_type") or "receipt"),
        "document_number": str(data.get("document_number")).strip()
        if data.get("document_number")
        else None,
        "document_date": str(data.get("document_date") or "")[:10] or None,
        "vendor_name": vendor,
        "total_amount": str(data.get("total_amount") or "").strip() or None,
        "tax_amount": str(tax).strip() if tax else None,
        "currency": str(data.get("currency") or "SGD"),
        "exchange_rate": str(data.get("exchange_rate")).strip()
        if data.get("exchange_rate")
        else None,
        "business_purpose": str(data.get("business_purpose") or data.get("purpose") or "").strip()
        or None,
        "sender_validated": "true" if validated else "false",
        "sgd_amount": str(data.get("sgd_amount") or data.get("total_amount") or ""),
    }
