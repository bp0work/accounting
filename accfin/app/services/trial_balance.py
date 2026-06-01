"""Trial balance report — all active COA accounts with posted journal totals."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import CoaAccount, JournalEntry, JournalEntryLine
from app.schemas.trial_balance import TrialBalanceGroup, TrialBalanceResponse, TrialBalanceRow

_ACCOUNT_TYPE_ORDER = ("asset", "liability", "equity", "revenue", "expense")

_GROUP_LABELS = {
    "asset": "ASSET",
    "liability": "LIABILITY",
    "equity": "EQUITY",
    "revenue": "REVENUE",
    "expense": "EXPENSE",
}


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def format_trial_balance_amount(value: Decimal) -> str | None:
    """Return 2dp string for non-zero amounts; None for zero (UI/CSV em dash)."""
    q = _quantize(value)
    if q == 0:
        return None
    return f"{q:.2f}"


def format_trial_balance_balance(debit: Decimal, credit: Decimal) -> str:
    """Balance = debit - credit; negatives as (12.90)."""
    balance = _quantize(debit - credit)
    if balance == 0:
        return "0.00"
    if balance < 0:
        return f"({abs(balance):.2f})"
    return f"{balance:.2f}"


def format_trial_balance_total(balance: Decimal) -> str:
    """Group or grand total balance."""
    q = _quantize(balance)
    if q == 0:
        return "0.00"
    if q < 0:
        return f"({abs(q):.2f})"
    return f"{q:.2f}"


async def build_trial_balance(
    session: AsyncSession, *, as_at: date
) -> TrialBalanceResponse:
    line_totals = (
        select(
            JournalEntryLine.account_id.label("account_id"),
            func.coalesce(func.sum(JournalEntryLine.debit), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit), 0).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(JournalEntry.status == "posted", JournalEntry.entry_date <= as_at)
        .group_by(JournalEntryLine.account_id)
        .subquery()
    )

    result = await session.execute(
        select(
            CoaAccount.account_code,
            CoaAccount.account_name,
            CoaAccount.account_type,
            func.coalesce(line_totals.c.total_debit, 0).label("total_debit"),
            func.coalesce(line_totals.c.total_credit, 0).label("total_credit"),
        )
        .outerjoin(line_totals, line_totals.c.account_id == CoaAccount.id)
        .where(CoaAccount.is_active.is_(True))
        .order_by(CoaAccount.account_type, CoaAccount.account_code)
    )

    rows_by_type: dict[str, list[TrialBalanceRow]] = {t: [] for t in _ACCOUNT_TYPE_ORDER}
    balance_by_type: dict[str, Decimal] = {t: Decimal("0") for t in _ACCOUNT_TYPE_ORDER}

    for row in result.all():
        debit = Decimal(str(row.total_debit))
        credit = Decimal(str(row.total_credit))
        balance = _quantize(debit - credit)
        account_type = row.account_type
        if account_type not in rows_by_type:
            rows_by_type[account_type] = []
            balance_by_type[account_type] = Decimal("0")
        rows_by_type[account_type].append(
            TrialBalanceRow(
                account_code=row.account_code,
                account_name=row.account_name,
                debit=format_trial_balance_amount(debit),
                credit=format_trial_balance_amount(credit),
                balance=format_trial_balance_balance(debit, credit),
            )
        )
        balance_by_type[account_type] += balance

    groups: list[TrialBalanceGroup] = []
    grand_total = Decimal("0")
    for account_type in _ACCOUNT_TYPE_ORDER:
        type_rows = rows_by_type.get(account_type, [])
        if not type_rows:
            continue
        type_total = balance_by_type.get(account_type, Decimal("0"))
        grand_total += type_total
        groups.append(
            TrialBalanceGroup(
                account_type=account_type,
                label=_GROUP_LABELS[account_type],
                rows=type_rows,
                total_balance=format_trial_balance_total(type_total),
            )
        )

    return TrialBalanceResponse(
        as_at=as_at,
        groups=groups,
        grand_total_balance=format_trial_balance_total(grand_total),
    )


def trial_balance_to_csv(report: TrialBalanceResponse) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([f"Trial Balance — As at {report.as_at.strftime('%d/%m/%Y')}"])
    writer.writerow([])

    for group in report.groups:
        writer.writerow([group.label])
        writer.writerow(
            ["Account Code", "Account Name", "Debit", "Credit", "Balance"]
        )
        for row in group.rows:
            writer.writerow(
                [
                    row.account_code,
                    row.account_name,
                    row.debit or "—",
                    row.credit or "—",
                    row.balance,
                ]
            )
        writer.writerow(["", "", "", "Total", group.total_balance])
        writer.writerow([])

    writer.writerow(["", "", "", "TOTAL", report.grand_total_balance])
    return buffer.getvalue()
