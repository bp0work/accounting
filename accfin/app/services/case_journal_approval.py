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
from app.schemas.journal_entry import JournalEntryApprovalDetail, JournalEntryLineDetail
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


async def _lines_for_entry(
    session: AsyncSession, entry: JournalEntry
) -> tuple[list[JournalEntryLineDetail], str | None, str | None, str | None, str | None]:
    """Build line details and primary expense (debit) / payable (credit) account labels."""
    if not entry.lines:
        return [], None, None, None, None

    account_ids = {line.account_id for line in entry.lines}
    result = await session.execute(select(CoaAccount).where(CoaAccount.id.in_(account_ids)))
    by_id = {row.id: row for row in result.scalars().all()}

    line_details: list[JournalEntryLineDetail] = []
    expense_account_id: str | None = None
    payable_account_id: str | None = None
    debit_name: str | None = None
    credit_name: str | None = None

    for line in sorted(entry.lines, key=lambda ln: ln.line_number):
        account = by_id.get(line.account_id)
        code = account.account_code if account else None
        name = account.account_name if account else None
        line_details.append(
            JournalEntryLineDetail(
                line_number=line.line_number,
                account_id=str(line.account_id),
                account_code=code,
                account_name=name,
                debit=_format_money(line.debit) if line.debit else None,
                credit=_format_money(line.credit) if line.credit else None,
                description=line.description,
            )
        )
        if account is None:
            continue
        label = f"{account.account_code} — {account.account_name}"
        if line.debit > 0 and account.account_type == "expense" and expense_account_id is None:
            expense_account_id = str(account.id)
            debit_name = label
        if line.credit > 0 and account.account_type == "liability" and payable_account_id is None:
            payable_account_id = str(account.id)
            credit_name = label

    return line_details, expense_account_id, payable_account_id, debit_name, credit_name


def _parse_formatted_money(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except Exception:
        return None


def _amounts_from_journal_lines(
    lines: list[JournalEntryLineDetail],
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Derive ex-GST, GST, and inclusive total from draft journal lines."""
    net: Decimal | None = None
    gst: Decimal | None = None
    total_credit = Decimal("0")
    has_credit = False
    for line in lines:
        if line.debit:
            debit_val = _parse_formatted_money(line.debit)
            if debit_val is None:
                continue
            if line.account_code == "2011":
                gst = (gst or Decimal("0")) + debit_val
            elif line.line_number == 1:
                net = debit_val
        if line.credit:
            credit_val = _parse_formatted_money(line.credit)
            if credit_val is not None:
                total_credit += credit_val
                has_credit = True
    gross = total_credit if has_credit else None
    return net, gst, gross


def _detail_from_metadata(meta: dict) -> JournalEntryApprovalDetail | None:
    raw = meta.get("journal_entry")
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return JournalEntryApprovalDetail.model_validate(raw)
    except Exception:
        return None


def _stored_lines_usable(lines: list[JournalEntryLineDetail]) -> bool:
    """Cached workflow_metadata lines must include account_id for COA dropdowns."""
    if not lines:
        return False
    return all(ln.account_id and str(ln.account_id).strip() for ln in lines)


async def build_journal_entry_approval_detail(
    session: AsyncSession, case: Case
) -> JournalEntryApprovalDetail | None:
    if case.status not in _APPROVAL_CASE_STATUSES:
        return None

    meta = _meta_dict(case)
    stored = _detail_from_metadata(meta)
    if stored is not None and _stored_lines_usable(stored.lines):
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
    document_number = _str_val(extracted.get("document_number"))
    document_date = _str_val(extracted.get("document_date"))
    document_type = _document_type_label(_str_val(extracted.get("document_type")))

    amount: Decimal | None = None
    gst: Decimal | None = None
    if case.amount_value is not None:
        amount = Decimal(str(case.amount_value))
    elif extracted.get("total_amount") not in (None, ""):
        amount = Decimal(str(extracted.get("total_amount")))
    elif extracted.get("sgd_amount") not in (None, ""):
        amount = Decimal(str(extracted.get("sgd_amount")))

    tax_raw = extracted.get("tax_amount")
    if tax_raw not in (None, ""):
        try:
            gst = Decimal(str(tax_raw))
        except Exception:
            gst = None

    debit_account: str | None = None
    credit_account: str | None = None
    expense_account_id: str | None = None
    payable_account_id: str | None = None
    lines: list[JournalEntryLineDetail] = []
    journal_entry_id = _str_val(meta.get("journal_entry_id"))
    entry_number: str | None = None

    entry = await _load_draft_entry(session, case.id)
    if entry is not None:
        journal_entry_id = str(entry.id)
        entry_number = entry.entry_number
        if amount is None and entry.total_debit:
            amount = entry.total_debit
        lines, expense_account_id, payable_account_id, debit_account, credit_account = (
            await _lines_for_entry(session, entry)
        )
        if gst is None:
            for ld in lines:
                if ld.account_code == "2011" and ld.debit:
                    try:
                        gst = Decimal(ld.debit.replace(",", ""))
                    except Exception:
                        pass
                    break

    if debit_account is None:
        code = _str_val(meta.get("expense_account_code"))
        if code:
            debit_account = code

    if credit_account is None:
        credit_account = "Due to employee"

    gross = amount
    net = amount
    if lines:
        line_net, line_gst, line_gross = _amounts_from_journal_lines(lines)
        if line_net is not None:
            net = line_net
        if line_gst is not None and line_gst > 0:
            gst = line_gst
        if line_gross is not None:
            gross = line_gross
    elif gross is not None and gst is not None and gst > 0 and gst < gross:
        net = gross - gst

    return JournalEntryApprovalDetail(
        vendor=vendor,
        document_number=document_number,
        document_date=document_date,
        document_type=document_type,
        amount_sgd=_format_money(net, currency),
        gst=_format_money(gst, currency) if gst and gst > 0 else None,
        total=_format_money(gross, currency),
        debit_account=debit_account,
        credit_account=credit_account,
        expense_account_id=expense_account_id,
        payable_account_id=payable_account_id,
        lines=lines,
        approval_tier_label=_tier_label(tier_int, thresholds, currency),
        journal_entry_id=journal_entry_id,
        entry_number=entry_number,
    )
