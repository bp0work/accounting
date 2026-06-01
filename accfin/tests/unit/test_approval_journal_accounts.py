"""Journal account overrides on approval — `0.14.72`."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.case import Case
from app.models.ledger import CoaAccount, JournalEntry, JournalEntryLine
from app.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_approve_updates_draft_journal_line_accounts(db_session, test_user) -> None:
    expense = CoaAccount(
        account_code=f"6{uuid4().hex[:4]}",
        account_name="Travel",
        account_type="expense",
        is_active=True,
    )
    expense_alt = CoaAccount(
        account_code=f"6{uuid4().hex[:4]}",
        account_name="Meals",
        account_type="expense",
        is_active=True,
    )
    payable = CoaAccount(
        account_code=f"2{uuid4().hex[:4]}",
        account_name="Staff payable",
        account_type="liability",
        is_active=True,
    )
    payable_alt = CoaAccount(
        account_code=f"2{uuid4().hex[:4]}",
        account_name="Staff payable alt",
        account_type="liability",
        is_active=True,
    )
    db_session.add_all([expense, expense_alt, payable, payable_alt])
    await db_session.flush()

    case = Case(
        case_number=f"CAS-JA-{uuid4().hex[:8]}",
        type="expense_claim",
        status="pending_approval",
        subject="Journal account edit test",
    )
    db_session.add(case)
    await db_session.flush()

    entry = JournalEntry(
        entry_number=f"JE-{uuid4().hex[:8]}",
        case_id=case.id,
        case_number=case.case_number,
        status="draft",
        entry_date=case.created_at.date(),
        description="Test",
        reference=case.case_number,
        currency="SGD",
        total_debit=Decimal("115.00"),
        total_credit=Decimal("115.00"),
        is_balanced=True,
    )
    db_session.add(entry)
    await db_session.flush()
    db_session.add_all(
        [
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_number=1,
                account_id=expense.id,
                debit=Decimal("100.00"),
                credit=Decimal("0"),
            ),
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_number=2,
                account_id=payable.id,
                debit=Decimal("0"),
                credit=Decimal("115.00"),
            ),
        ]
    )
    await db_session.flush()

    service = ApprovalService(db_session)
    await service._apply_draft_journal_account_overrides(
        case.id,
        debit_account_id=expense_alt.id,
        credit_account_id=payable_alt.id,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(JournalEntry)
        .where(JournalEntry.id == entry.id)
        .options(selectinload(JournalEntry.lines))
    )
    saved = result.scalar_one()
    by_no = {ln.line_number: ln for ln in saved.lines}
    assert by_no[1].account_id == expense_alt.id
    assert by_no[2].account_id == payable_alt.id
