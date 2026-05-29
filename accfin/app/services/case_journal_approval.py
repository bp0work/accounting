"""Build journal entry approval summary for Finance UI case detail."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import Case
from app.models.ledger import CoaAccount, JournalEntry
from app.policies.binding_authority import BindingAuthorityThresholds
from app.schemas.journal_entry import JournalEntryApprovalDetail
from app.services.binding_authority_service import BindingAuthorityService

_APPROVAL_CASE_STATUSES = frozenset({"pending_approval", "journal_pending_approval"})

_DOCUMENT_TYPE_LABELS = {
    "invoice": "Invoice",
    "credit_note": "Credit note",
    "debit_note": "Debit note",
}


def _meta_dict(case: Case) -> dict:
    raw = case.workflow_metadata or {}
    return raw if isinstance(raw, dict) else {}


def _str_val(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_money(amount: Decimal | None, currency: str = "SGD") -> str | None:
    if amount is None:
        return None
    return f"{amount:,.2f}"


def _tier_label(tier: int | None, thresholds: BindingAuthorityThresholds, currency: str) -> str | None:
    if tier is None:
        return None
    c = currency or "SGD"
    t1 = thresholds.tier_1_ceiling
    t2 = thresholds.tier_2_ceiling
    t3 = thresholds.tier_3_threshold
    if tier <= 1:
        return f"Tier 1 ({c} up to {t1:,.0f})"
    if tier == 2:
        low = int(t1) + 1
        return f"Tier {tier} ({c} {low:,} – {t2:,.0f})"
    return f"Tier {tier} (above {c} {t3:,.0f})"


def _document_type_label(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _DOCUMENT_TYPE_LABELS.get(key, raw.replace("_", " ").title())


async def _load_draft_entry(session: AsyncSession, case_id: UUID) -> JournalEntry | None:
    result = await session.execute(
        select(JournalEntry)
        .where(JournalEntry.case_id == case_id, JournalEntry.status == "draft")
        .order_by(JournalEntry.created_at.desc())
        .limit(1)
        .options(selectinload(JournalEntry.lines))
    )
    return result.scalar_one_or_none()


async def _account_names_for_entry(
    session: AsyncSession, entry: JournalEntry
) -> tuple[str | None, str | None]:
    if not entry.lines:
        return None, None
    account_ids = {line.account_id for line in entry.lines}
    result = await session.execute(select(CoaAccount).where(CoaAccount.id.in_(account_ids)))
    by_id = {row.id: row for row in result.scalars().all()}

    debit_name: str | None = None
    credit_name: str | None = None
    max_debit = Decimal("-1")
    max_credit = Decimal("-1")
    for line in entry.lines:
        account = by_id.get(line.account_id)
        if account is None:
            continue
        label = f"{account.account_code} — {account.account_name}"
        if line.debit > max_debit:
            max_debit = line.debit
            debit_name = account.account_name
        if line.credit > max_credit:
            max_credit = line.credit
            credit_name = account.account_name
    return debit_name, credit_name


def _detail_from_metadata(meta: dict) -> JournalEntryApprovalDetail | None:
    raw = meta.get("journal_entry")
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return JournalEntryApprovalDetail.model_validate(raw)
    except Exception:
        return None


async def build_journal_entry_approval_detail(
    session: AsyncSession, case: Case
) -> JournalEntryApprovalDetail | None:
    if case.status not in _APPROVAL_CASE_STATUSES:
        return None

    meta = _meta_dict(case)
    stored = _detail_from_metadata(meta)
    if stored is not None:
        return stored

    extracted = meta.get("extracted_fields") or {}
    if not isinstance(extracted, dict):
        extracted = {}

    tier = case.current_approval_tier or meta.get("policy_tier") or meta.get("binding_authority_tier")
    try:
        tier_int = int(tier) if tier is not None else None
    except (TypeError, ValueError):
        tier_int = None

    binding = BindingAuthorityService(session)
    thresholds = await binding.get_thresholds(case.type)
    currency = _str_val(case.amount_currency) or _str_val(extracted.get("currency")) or "SGD"

    vendor = (
        _str_val(case.counterparty_name)
        or _str_val(extracted.get("vendor_name"))
        or _str_val(meta.get("vendor_name"))
    )
    invoice_number = _str_val(extracted.get("invoice_number")) or _str_val(
        extracted.get("document_number")
    )
    invoice_date = _str_val(extracted.get("invoice_date")) or _str_val(
        extracted.get("document_date")
    )
    document_type = _document_type_label(_str_val(extracted.get("document_type")))

    amount: Decimal | None = None
    gst: Decimal | None = None
    if case.amount_value is not None:
        amount = Decimal(str(case.amount_value))
    elif extracted.get("total_amount") not in (None, ""):
        amount = Decimal(str(extracted.get("total_amount")))
    elif extracted.get("sgd_amount") not in (None, ""):
        amount = Decimal(str(extracted.get("sgd_amount")))

    gst_raw = extracted.get("gst_amount") or extracted.get("tax_amount")
    if gst_raw not in (None, ""):
        try:
            gst = Decimal(str(gst_raw))
        except Exception:
            gst = None

    debit_account: str | None = None
    credit_account: str | None = None
    journal_entry_id = _str_val(meta.get("journal_entry_id"))
    entry_number: str | None = None

    entry = await _load_draft_entry(session, case.id)
    if entry is not None:
        journal_entry_id = str(entry.id)
        entry_number = entry.entry_number
        if amount is None and entry.total_debit:
            amount = entry.total_debit
        debit_account, credit_account = await _account_names_for_entry(session, entry)

    if debit_account is None:
        code = _str_val(meta.get("expense_account_code"))
        if code:
            debit_account = code

    if credit_account is None:
        credit_account = "Trade Creditors"

    gross = amount
    net = amount
    if gross is not None and gst is not None and gst < gross:
        net = gross - gst

    return JournalEntryApprovalDetail(
        vendor=vendor,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        document_type=document_type,
        amount_sgd=_format_money(net, currency),
        gst=_format_money(gst, currency),
        total=_format_money(gross, currency),
        debit_account=debit_account,
        credit_account=credit_account,
        approval_tier_label=_tier_label(tier_int, thresholds, currency),
        journal_entry_id=journal_entry_id,
        entry_number=entry_number,
    )
