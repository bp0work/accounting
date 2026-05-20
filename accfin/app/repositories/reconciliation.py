"""Reconciliation persistence — `06` §12."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import CoaAccount, JournalEntry, JournalEntryLine
from app.models.reconciliation import (
    ReconciliationBankItem,
    ReconciliationLedgerItem,
    ReconciliationMatch,
    ReconciliationRun,
)


class ReconciliationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_run(self, run_id: UUID) -> ReconciliationRun | None:
        return await self._session.get(ReconciliationRun, run_id)

    async def get_account(self, account_id: UUID) -> CoaAccount | None:
        return await self._session.get(CoaAccount, account_id)

    async def create_run(
        self,
        *,
        account_id: UUID,
        period_from: date,
        period_to: date,
        started_by: UUID,
        opening_balance: Decimal = Decimal("0"),
        statement_balance: Decimal | None = None,
    ) -> ReconciliationRun:
        run = ReconciliationRun(
            account_id=account_id,
            statement_period_from=period_from,
            statement_period_to=period_to,
            started_by=started_by,
            opening_balance=opening_balance,
            statement_balance=statement_balance,
            status="in_progress",
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def add_bank_items(
        self, run_id: UUID, items: list[dict]
    ) -> list[ReconciliationBankItem]:
        rows = []
        for item in items:
            row = ReconciliationBankItem(
                reconciliation_run_id=run_id,
                transaction_date=item["transaction_date"],
                description=item.get("description"),
                reference=item.get("reference"),
                amount=Decimal(str(item["amount"])),
                currency=item.get("currency", "SGD"),
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    async def load_ledger_items_from_journals(
        self, run_id: UUID, account_id: UUID, period_from: date, period_to: date
    ) -> list[ReconciliationLedgerItem]:
        result = await self._session.execute(
            select(JournalEntryLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.account_id == account_id,
                JournalEntry.entry_date >= period_from,
                JournalEntry.entry_date <= period_to,
                JournalEntry.status == "posted",
            )
            .order_by(JournalEntry.entry_date)
        )
        rows: list[ReconciliationLedgerItem] = []
        for line, entry in result.all():
            amount = line.debit if line.debit > 0 else line.credit
            if amount == 0:
                continue
            row = ReconciliationLedgerItem(
                reconciliation_run_id=run_id,
                journal_entry_id=entry.id,
                journal_entry_line_id=line.id,
                transaction_date=entry.entry_date,
                description=entry.description,
                reference=entry.reference,
                amount=amount,
                currency=entry.currency,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return rows

    async def set_run_totals(self, run: ReconciliationRun) -> None:
        bank_count = await self._session.scalar(
            select(func.count())
            .select_from(ReconciliationBankItem)
            .where(ReconciliationBankItem.reconciliation_run_id == run.id)
        )
        ledger_count = await self._session.scalar(
            select(func.count())
            .select_from(ReconciliationLedgerItem)
            .where(ReconciliationLedgerItem.reconciliation_run_id == run.id)
        )
        run.total_bank_transactions = int(bank_count or 0)
        run.total_ledger_transactions = int(ledger_count or 0)
        await self._session.flush()

    async def list_unmatched_bank(self, run_id: UUID) -> list[ReconciliationBankItem]:
        result = await self._session.execute(
            select(ReconciliationBankItem)
            .where(
                ReconciliationBankItem.reconciliation_run_id == run_id,
                ReconciliationBankItem.is_matched.is_(False),
            )
            .order_by(ReconciliationBankItem.transaction_date)
        )
        return list(result.scalars().all())

    async def list_unmatched_ledger(self, run_id: UUID) -> list[ReconciliationLedgerItem]:
        result = await self._session.execute(
            select(ReconciliationLedgerItem)
            .where(
                ReconciliationLedgerItem.reconciliation_run_id == run_id,
                ReconciliationLedgerItem.is_matched.is_(False),
            )
            .order_by(ReconciliationLedgerItem.transaction_date)
        )
        return list(result.scalars().all())

    async def record_auto_match(
        self,
        run_id: UUID,
        bank_item_id: UUID,
        ledger_item_id: UUID,
        *,
        confidence: Decimal,
        match_reason: str,
    ) -> ReconciliationMatch:
        match = ReconciliationMatch(
            reconciliation_run_id=run_id,
            bank_item_id=bank_item_id,
            ledger_item_id=ledger_item_id,
            match_type="auto",
            confidence=confidence,
            match_reason=match_reason,
            matched_at=datetime.now(UTC),
        )
        self._session.add(match)
        await self._session.flush()

        bank = await self._session.get(ReconciliationBankItem, bank_item_id)
        ledger = await self._session.get(ReconciliationLedgerItem, ledger_item_id)
        if bank:
            bank.is_matched = True
            bank.match_id = match.id
            bank.match_type = "auto"
        if ledger:
            ledger.is_matched = True
            ledger.match_id = match.id
            ledger.match_type = "auto"
        await self._session.flush()
        return match

    async def record_pending_ai_match(
        self,
        run_id: UUID,
        bank_item_id: UUID,
        ledger_item_id: UUID,
        *,
        confidence: Decimal,
        match_reason: str,
    ) -> ReconciliationMatch:
        match = ReconciliationMatch(
            reconciliation_run_id=run_id,
            bank_item_id=bank_item_id,
            ledger_item_id=ledger_item_id,
            match_type="manual",
            confidence=confidence,
            match_reason=match_reason,
            matched_at=datetime.now(UTC),
        )
        self._session.add(match)
        await self._session.flush()
        return match

    async def complete_run(self, run: ReconciliationRun, rules_used: list[str]) -> None:
        result = await self._session.execute(
            select(ReconciliationMatch).where(
                ReconciliationMatch.reconciliation_run_id == run.id,
                ReconciliationMatch.is_voided.is_(False),
            )
        )
        matches = list(result.scalars().all())
        total_matched = len(matches)
        auto_count = sum(1 for m in matches if m.match_type == "auto")
        manual_count = sum(1 for m in matches if m.match_type == "manual")

        bank_sum = await self._session.scalar(
            select(func.coalesce(func.sum(ReconciliationBankItem.amount), 0)).where(
                ReconciliationBankItem.reconciliation_run_id == run.id
            )
        )

        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.matched_count = int(total_matched or 0)
        run.auto_matched_count = int(auto_count or 0)
        run.manual_matched_count = int(manual_count or 0)
        run.unmatched_count = max(run.total_bank_transactions - run.matched_count, 0)
        if run.total_bank_transactions:
            run.match_rate = Decimal(run.matched_count) / Decimal(run.total_bank_transactions)
        else:
            run.match_rate = Decimal("0")
        run.closing_balance = run.opening_balance + Decimal(bank_sum or 0)
        run.match_rules_used = rules_used
        await self._session.flush()

    async def fail_run(self, run: ReconciliationRun, error_message: str) -> None:
        run.status = "failed"
        run.error_message = error_message[:500]
        await self._session.flush()
