"""Unit tests for expense policy evaluation — `19` §5."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.expense_policy_evaluator import evaluate_expense_claim


def _line(*, amount: str, category: str = "meals", receipt: bool = True):
    return SimpleNamespace(
        id=uuid4(),
        category=category,
        amount_claimed=Decimal(amount),
        amount_sgd=Decimal(amount),
        receipt_attachment_id=uuid4() if receipt else None,
    )


def test_stp_eligible_small_claim():
    policies = [
        SimpleNamespace(
            is_active=True,
            applies_to_all_categories=True,
            requires_receipt_above=Decimal("50"),
            requires_approval_above=Decimal("500"),
            category=None,
            daily_limit=None,
            name="global",
        )
    ]
    result = evaluate_expense_claim(
        line_items=[_line(amount="45")],
        total_claimed=Decimal("45"),
        confidence=0.95,
        policies=policies,
        submission_date=date(2026, 5, 10),
        claim_period_to=date(2026, 5, 9),
    )
    assert result.stp_eligible is True
    assert result.tier == 1


def test_receipt_missing_breaks_stp():
    policies = [
        SimpleNamespace(
            is_active=True,
            applies_to_all_categories=True,
            requires_receipt_above=Decimal("50"),
            requires_approval_above=Decimal("500"),
            category=None,
            daily_limit=None,
            name="global",
        )
    ]
    result = evaluate_expense_claim(
        line_items=[_line(amount="120", receipt=False)],
        total_claimed=Decimal("120"),
        confidence=0.95,
        policies=policies,
        submission_date=date(2026, 5, 10),
        claim_period_to=date(2026, 5, 9),
    )
    assert result.stp_eligible is False
    assert "receipt_missing" in result.risk_flags
    assert result.tier >= 2


def test_meals_daily_limit_violation():
    policies = [
        SimpleNamespace(
            is_active=True,
            applies_to_all_categories=False,
            requires_receipt_above=Decimal("30"),
            requires_approval_above=Decimal("500"),
            category="meals",
            daily_limit=Decimal("80"),
            name="meals_daily_limit",
        )
    ]
    result = evaluate_expense_claim(
        line_items=[_line(amount="100", category="meals")],
        total_claimed=Decimal("100"),
        confidence=0.92,
        policies=policies,
        submission_date=date(2026, 5, 10),
        claim_period_to=date(2026, 5, 9),
    )
    assert "amount_exceeds_daily_limit" in result.risk_flags
    assert result.stp_eligible is False
