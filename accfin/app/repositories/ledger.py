"""COA and journal persistence — Phase 6."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import CoaAccount, JournalEntry, JournalEntryLine


class LedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_account_by_code(self, code: str) -> CoaAccount | None:
        result = await self._session.execute(
            select(CoaAccount).where(
                CoaAccount.account_code == code, CoaAccount.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def get_account_by_id(self, account_id: UUID) -> CoaAccount | None:
        result = await self._session.execute(
            select(CoaAccount).where(
                CoaAccount.id == account_id, CoaAccount.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def next_entry_number(self) -> str:
        year = datetime.now(UTC).year
        prefix = f"JE-{year}-"
        result = await self._session.execute(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.entry_number.like(f"{prefix}%"))
        )
        seq = int(result.scalar_one() or 0) + 1
        return f"{prefix}{seq:06d}"

    async def create_journal_entry(
        self,
        *,
        case_id: UUID,
        case_number: str,
        status: str,
        entry_date: date,
        description: str,
        reference: str | None,
        currency: str,
        total: Decimal,
        posted: bool,
        metadata: dict | None = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            entry_number=await self.next_entry_number(),
            case_id=case_id,
            case_number=case_number,
            status=status,
            entry_date=entry_date,
            posting_date=entry_date if posted else None,
            description=description,
            reference=reference,
            currency=currency,
            total_debit=total,
            total_credit=total,
            is_balanced=True,
            posted_at=datetime.now(UTC) if posted else None,
            extra_metadata=metadata or {},
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def add_line(
        self,
        *,
        entry: JournalEntry,
        line_number: int,
        account_id: UUID,
        debit: Decimal,
        credit: Decimal,
        description: str | None = None,
    ) -> JournalEntryLine:
        line = JournalEntryLine(
            journal_entry_id=entry.id,
            line_number=line_number,
            account_id=account_id,
            debit=debit,
            credit=credit,
            description=description,
        )
        self._session.add(line)
        await self._session.flush()
        return line
