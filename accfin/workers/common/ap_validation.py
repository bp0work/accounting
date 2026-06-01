"""AP workflow validation helpers — sender validation, dedup, vendor, payment terms.

AP Process document §Steps 1–5.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.utils.hermes_amounts import decimal_from_hermes_amount
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, Counterparty
from app.models.counterparty_master import CounterpartyAccount, PaymentTerm

_VALIDATION_FAIL_REASON = (
    "Document not validated. Please include 'validated' followed by a date in your email "
    "(e.g. 'validated 24 Apr 2025', 'validated 24/04/2025', or 'validated 24-04-2025')"
)

# Captures the date token immediately after "validated" (several accepted formats).
_VALIDATED_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bvalidated\s+(\d{1,2}/\d{1,2}/\d{4})\b", re.IGNORECASE),
    re.compile(r"\bvalidated\s+(\d{1,2}-\d{1,2}-\d{4})\b", re.IGNORECASE),
    re.compile(r"\bvalidated\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", re.IGNORECASE),
)


def _parse_validated_date_token(raw: str) -> date | None:
    token = raw.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def extract_sender_validation(subject: str | None, body: str | None) -> dict:
    """
    Scan email subject and body for "validated" + a parseable date.

    Accepted examples: validated 24 Apr 2025, validated 24 April 2025,
    validated 24/04/2025, validated 24-04-2025.

    Returns dict with keys:
      sender_validated (bool), validation_date (ISO str | None), failure_reason (str | None)
    """
    combined = " ".join(filter(None, [subject or "", body or ""]))
    if "validated" not in combined.lower():
        return {
            "sender_validated": False,
            "validation_date": None,
            "failure_reason": _VALIDATION_FAIL_REASON,
        }

    for pattern in _VALIDATED_DATE_PATTERNS:
        for match in pattern.finditer(combined):
            parsed = _parse_validated_date_token(match.group(1))
            if parsed is not None:
                return {
                    "sender_validated": True,
                    "validation_date": parsed.isoformat(),
                    "failure_reason": None,
                }

    return {
        "sender_validated": False,
        "validation_date": None,
        "failure_reason": _VALIDATION_FAIL_REASON,
    }


def resolve_ap_sgd_amount(extracted: dict) -> tuple[Decimal, dict, bool]:
    """Convert invoice total to SGD for GL posting.

    Returns ``(sgd_amount, updated_extracted, needs_escalation)``.
    """
    fields = dict(extracted)
    currency = str(fields.get("currency") or "SGD").strip().upper()
    try:
        total = decimal_from_hermes_amount(fields.get("total_amount"))
    except (InvalidOperation, ValueError):
        total = Decimal("0")

    if currency == "SGD":
        fields["sgd_amount"] = str(total)
        return total, fields, False

    rate_raw = fields.get("exchange_rate")
    if rate_raw not in (None, ""):
        try:
            rate = decimal_from_hermes_amount(rate_raw)
            if rate <= 0:
                raise InvalidOperation("non-positive rate")
            sgd = (total * rate).quantize(Decimal("0.01"))
            fields.update(
                {
                    "foreign_currency": currency,
                    "foreign_amount": str(total),
                    "exchange_rate": str(rate),
                    "sgd_amount": str(sgd),
                }
            )
            return sgd, fields, False
        except (InvalidOperation, ValueError):
            pass

    return Decimal("0"), fields, True


async def check_duplicate_by_fields(
    session: AsyncSession,
    *,
    vendor_name: str,
    document_number: str,
    total_amount: Decimal | None,
    exclude_case_id: UUID | None = None,
    days: int = 90,
) -> tuple[bool, str | None]:
    """Return (is_duplicate, existing_case_number).

    Matches ap_invoice cases with same vendor + document number + amount within last N days.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    q = (
        select(Case)
        .where(
            Case.counterparty_name.ilike(f"%{vendor_name}%"),
            Case.type == "ap_invoice",
            Case.created_at >= cutoff,
        )
        .order_by(Case.created_at.desc())
        .limit(100)
    )
    if exclude_case_id:
        q = q.where(Case.id != exclude_case_id)

    result = await session.execute(q)
    for existing in result.scalars().all():
        meta = existing.workflow_metadata or {}
        extracted = meta.get("extracted_fields") or {}
        inv_num = (
            extracted.get("document_number")
            or meta.get("document_number")
        )
        if not inv_num:
            continue
        if str(inv_num).strip().lower() != document_number.strip().lower():
            continue
        if total_amount is not None and existing.amount_value is not None:
            if abs(float(existing.amount_value) - float(total_amount)) > 0.01:
                continue
        return True, existing.case_number

    return False, None


async def lookup_vendor(
    session: AsyncSession,
    vendor_name: str,
    uen: str | None = None,
) -> tuple[Counterparty | None, CounterpartyAccount | None, str]:
    """
    Locate counterparty and primary bill_to subaccount.

    Returns (counterparty, subaccount, status) where status is
    'active', 'inactive', or 'not_found'.
    """
    cp: Counterparty | None = None

    if uen:
        result = await session.execute(
            select(Counterparty).where(Counterparty.code == uen)
        )
        cp = result.scalar_one_or_none()

    if cp is None:
        result = await session.execute(
            select(Counterparty)
            .where(Counterparty.name.ilike(f"%{vendor_name}%"))
            .order_by(Counterparty.name.asc())
            .limit(5)
        )
        rows = list(result.scalars().all())
        if not rows:
            return None, None, "not_found"
        exact = next((r for r in rows if r.name.lower() == vendor_name.lower()), None)
        cp = exact or rows[0]

    sub = await _primary_subaccount(session, cp.id)
    if sub is None:
        return cp, None, "not_found"
    return cp, sub, "active" if sub.is_active else "inactive"


async def _primary_subaccount(
    session: AsyncSession, counterparty_id: UUID
) -> CounterpartyAccount | None:
    result = await session.execute(
        select(CounterpartyAccount)
        .where(CounterpartyAccount.counterparty_id == counterparty_id)
        .order_by(
            CounterpartyAccount.is_active.desc(),
            CounterpartyAccount.role.asc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_payment_term(
    session: AsyncSession, payment_term_id: UUID
) -> PaymentTerm | None:
    result = await session.execute(
        select(PaymentTerm).where(PaymentTerm.id == payment_term_id)
    )
    return result.scalar_one_or_none()


_TERMS_NORMALISE = {
    "immediate": "immediate",
    "due_on_receipt": "immediate",
    "cash_on_delivery": "immediate",
    "cod": "immediate",
    "net7": "net_7",
    "net 7": "net_7",
    "7 days": "net_7",
    "7days": "net_7",
    "net14": "net_14",
    "net 14": "net_14",
    "14 days": "net_14",
    "14days": "net_14",
    "net30": "net_30",
    "net 30": "net_30",
    "30 days": "net_30",
    "30days": "net_30",
    "net60": "net_60",
    "net 60": "net_60",
    "60 days": "net_60",
    "60days": "net_60",
    "net90": "net_90",
    "net 90": "net_90",
    "90 days": "net_90",
    "90days": "net_90",
}


def normalise_payment_terms(s: str | None) -> str | None:
    if not s:
        return None
    key = s.strip().lower().replace("-", "_").replace("_", " ").strip()
    # Try with underscores too
    canonical = _TERMS_NORMALISE.get(key) or _TERMS_NORMALISE.get(key.replace(" ", "_"))
    return canonical or key


def payment_terms_match(
    document_terms: str | None,
    subaccount_code: str | None,
) -> bool:
    """True if extracted document terms match the counterparty subaccount terms code."""
    if not document_terms or not subaccount_code:
        return True  # cannot compare → do not block
    return normalise_payment_terms(document_terms) == normalise_payment_terms(subaccount_code)
