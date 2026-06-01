"""Expense reversal workflow unit tests — `0.15.03-expense-reversal`."""

from calendar import month_name
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppHTTPException
from app.constants.tenant import TENANT_MMLOGISTIX
from app.models.accounting_period import AccountingPeriod
from app.models.case import Case
from app.models.ledger import CoaAccount, JournalEntry, JournalEntryLine
from app.models.rbac import Role
from app.models.user import User
from app.schemas.auth import TokenData
from app.services.case_expense_reversal import (
    execute_approve_reversal,
    execute_raise_reversal,
    execute_reject_reversal,
)


async def _seed_posted_expense_case(
    db_session,
    *,
    case_status: str = "case_closed",
    entry_date: date | None = None,
) -> tuple[Case, JournalEntry, CoaAccount, CoaAccount]:
    expense = CoaAccount(
        account_code=f"6{uuid4().hex[:4]}",
        account_name="Travel",
        account_type="expense",
        is_active=True,
    )
    payable = CoaAccount(
        account_code=f"2{uuid4().hex[:4]}",
        account_name="Staff payable",
        account_type="liability",
        is_active=True,
    )
    db_session.add_all([expense, payable])
    await db_session.flush()

    case = Case(
        case_number=f"CAS-REV-{uuid4().hex[:6]}",
        type="expense_claim",
        status=case_status,
        subject="Expense reversal test",
        counterparty_name="Test Vendor",
        amount_value=Decimal("29.43"),
        amount_currency="SGD",
        workflow_metadata={
            "extracted_fields": {"document_number": "43CE8E1D-0028"},
        },
    )
    db_session.add(case)
    await db_session.flush()

    posting = entry_date or date(2025, 9, 15)
    entry = JournalEntry(
        entry_number=f"JE-{uuid4().hex[:8]}",
        case_id=case.id,
        case_number=case.case_number,
        status="posted",
        entry_date=posting,
        posting_date=posting,
        description="Expense",
        reference=case.case_number,
        currency="SGD",
        total_debit=Decimal("29.43"),
        total_credit=Decimal("29.43"),
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
                debit=Decimal("27.50"),
                credit=Decimal("0"),
            ),
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_number=2,
                account_id=payable.id,
                debit=Decimal("0"),
                credit=Decimal("29.43"),
            ),
        ]
    )
    await db_session.commit()
    return case, entry, expense, payable


@pytest.mark.asyncio
async def test_raise_reversal_creates_mirrored_journal(db_session, accounts_manager_user) -> None:
    case, posted, expense, payable = await _seed_posted_expense_case(db_session)
    user = TokenData(
        user_id=accounts_manager_user.id,
        role="accounts_manager",
        permissions=["cases:write"],
    )

    result = await execute_raise_reversal(case.id, user=user, reason="Duplicate claim")

    assert result.reversal_case_number.startswith("CAS-")
    reversal = await db_session.get(Case, result.reversal_case_id)
    assert reversal is not None
    assert reversal.status == "pending_reversal_approval"
    assert reversal.parent_case_id == case.id

    draft_result = await db_session.execute(
        select(JournalEntry)
        .where(JournalEntry.case_id == reversal.id, JournalEntry.status == "draft")
        .options(selectinload(JournalEntry.lines))
    )
    draft = draft_result.scalar_one()
    assert draft.reference == f"REV-{case.case_number}"
    assert draft.entry_date == posted.entry_date
    by_no = {ln.line_number: ln for ln in draft.lines}
    assert by_no[1].debit == Decimal("0")
    assert by_no[1].credit == Decimal("27.50")
    assert by_no[1].account_id == expense.id
    assert by_no[2].debit == Decimal("29.43")
    assert by_no[2].credit == Decimal("0")
    assert by_no[2].account_id == payable.id


@pytest.mark.asyncio
async def test_approve_reversal_posts_journal(db_session) -> None:
    case, _, _, _ = await _seed_posted_expense_case(db_session)
    acc_user = TokenData(user_id=uuid4(), role="accounts_manager", permissions=["cases:write"])
    raised = await execute_raise_reversal(case.id, user=acc_user)

    cfo_role = await db_session.scalar(select(Role).where(Role.name == "cfo"))
    assert cfo_role is not None
    cfo = User(
        id=uuid4(),
        username=f"cfo_{uuid4().hex[:6]}",
        display_name="CFO Test",
        email=f"cfo_{uuid4().hex[:6]}@example.com",
        password_hash="x",
        role_id=cfo_role.id,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(cfo)
    await db_session.commit()

    cfo_user = TokenData(
        user_id=cfo.id, role="cfo", permissions=["approvals:admin", "cases:read"]
    )
    approved = await execute_approve_reversal(raised.reversal_case_id, user=cfo_user)

    assert approved.status == "reversed"
    entry = await db_session.get(JournalEntry, approved.journal_entry_id)
    assert entry is not None
    assert entry.status == "posted"
    assert entry.posted_at is not None

    reversal = await db_session.get(Case, raised.reversal_case_id)
    assert reversal is not None
    assert reversal.status == "reversed"
    original = await db_session.get(Case, case.id)
    assert original is not None
    assert (original.workflow_metadata or {}).get("reversed_by") == reversal.case_number


@pytest.mark.asyncio
async def test_approve_reversal_closed_period_requires_reason(db_session) -> None:
    closed_date = date(2025, 9, 10)
    case, _, _, _ = await _seed_posted_expense_case(db_session, entry_date=closed_date)
    period = AccountingPeriod(
        tenant_id=TENANT_MMLOGISTIX,
        period_year=2025,
        period_month=9,
        status="closed",
        period_type="monthly",
        gl_cutoff_date=date(2025, 9, 30),
    )
    db_session.add(period)
    await db_session.commit()

    acc_user = TokenData(user_id=uuid4(), role="accounts_manager", permissions=["cases:write"])
    raised = await execute_raise_reversal(case.id, user=acc_user)

    cfo_user = TokenData(user_id=uuid4(), role="cfo", permissions=["approvals:admin"])
    with pytest.raises(AppHTTPException) as exc:
        await execute_approve_reversal(raised.reversal_case_id, user=cfo_user)
    assert exc.value.status_code == 422
    label = f"{month_name[closed_date.month]} {closed_date.year}"
    assert label in exc.value.message

    approved = await execute_approve_reversal(
        raised.reversal_case_id,
        user=cfo_user,
        gl_period_override_reason="CFO approved year-end reversal",
    )
    assert approved.status == "reversed"


@pytest.mark.asyncio
async def test_reject_reversal_voids_draft_journal(db_session) -> None:
    case, _, _, _ = await _seed_posted_expense_case(db_session)
    acc_user = TokenData(user_id=uuid4(), role="accounts_manager", permissions=["cases:write"])
    raised = await execute_raise_reversal(case.id, user=acc_user)

    cfo_user = TokenData(user_id=uuid4(), role="cfo", permissions=["approvals:admin"])
    result = await execute_reject_reversal(
        raised.reversal_case_id, user=cfo_user, comment="Not justified"
    )
    assert result.status == "reversal_rejected"

    reversal = await db_session.get(Case, raised.reversal_case_id)
    assert reversal is not None
    assert reversal.status == "reversal_rejected"

    draft_result = await db_session.execute(
        select(JournalEntry).where(JournalEntry.case_id == reversal.id)
    )
    draft = draft_result.scalar_one()
    assert draft.status == "reversed"
    assert (draft.extra_metadata or {}).get("voided") is True
