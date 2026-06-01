"""Expense journal line amounts — ex-tax debit (`0.14.72`)."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.case import Case
from app.models.expense import ExpenseClaim
from workers.expense.handlers import ExpenseWorkerHandler


@pytest.mark.asyncio
async def test_create_expense_journal_uses_amount_minus_tax() -> None:
    handler = ExpenseWorkerHandler.__new__(ExpenseWorkerHandler)
    handler._ledger = AsyncMock()

    expense_acct = MagicMock(id=uuid4())
    gst_acct = MagicMock(id=uuid4())
    payable_acct = MagicMock(id=uuid4())
    entry = MagicMock(id=uuid4())
    handler._ledger.create_journal_entry = AsyncMock(return_value=entry)
    handler._ledger.add_line = AsyncMock()

    from datetime import date

    case = Case(case_number="CAS-EXP-1", type="expense_claim", status="processing")
    claim = ExpenseClaim(claimant_name="Test", total_claimed=Decimal("115"))

    await handler._create_expense_journal(
        case,
        claim,
        Decimal("115"),
        Decimal("15"),
        expense_account=expense_acct,
        gst_account=gst_acct,
        payable_account=payable_acct,
        posted=False,
        posting_date=date.today(),
    )

    debits = [call.kwargs["debit"] for call in handler._ledger.add_line.call_args_list]
    credits = [call.kwargs["credit"] for call in handler._ledger.add_line.call_args_list]
    assert debits[0] == Decimal("100")
    assert debits[1] == Decimal("15")
    assert credits[-1] == Decimal("115")
