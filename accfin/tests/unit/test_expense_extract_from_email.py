"""Expense worker Hermes extraction unwrap — `0.14.47-expense-extract-unwrap`."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.case import Case
from app.schemas.hermes import ExtractExpenseClaimOutput, ExtractedExpenseLineItem
from workers.expense.handlers import ExpenseWorkerService


@pytest.mark.asyncio
async def test_extract_from_email_uses_unwrapped_hermes_output() -> None:
    case = Case(
        id=uuid4(),
        case_number="EXP-001",
        type="expense_claim",
        status="processing",
        email_id=uuid4(),
    )
    hermes = MagicMock()
    hermes.extract_expense_claim = AsyncMock(
        return_value=ExtractExpenseClaimOutput(
            confidence_score=0.91,
            currency="SGD",
            purpose="Client lunch",
            line_items=[
                ExtractedExpenseLineItem(
                    line_number=1,
                    expense_date=date(2026, 5, 1),
                    category="meals",
                    merchant="Cafe One",
                    amount_claimed="42.50",
                )
            ],
        )
    )
    service = ExpenseWorkerService(session=MagicMock(), hermes=hermes)

    fields, confidence = await service._extract_from_email(case, email=None)

    assert confidence == pytest.approx(0.91)
    assert fields is not None
    assert fields["merchant_name"] == "Cafe One"
    assert fields["total_amount"] == "42.50"
    assert fields["expense_category"] == "meals"


@pytest.mark.asyncio
async def test_extract_from_email_empty_line_items_returns_none() -> None:
    case = Case(
        id=uuid4(),
        case_number="EXP-002",
        type="expense_claim",
        status="processing",
        email_id=uuid4(),
    )
    hermes = MagicMock()
    hermes.extract_expense_claim = AsyncMock(
        return_value=ExtractExpenseClaimOutput(confidence_score=0.5, line_items=[])
    )
    service = ExpenseWorkerService(session=MagicMock(), hermes=hermes)

    fields, confidence = await service._extract_from_email(case, email=None)

    assert fields is None
    assert confidence == pytest.approx(0.5)
