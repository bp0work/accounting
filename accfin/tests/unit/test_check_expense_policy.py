"""Unit tests — check_expense_policy (worker validation)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from workers.common.expense_validation import check_expense_policy


def _policy(**kwargs):
    defaults = {
        "is_active": True,
        "name": "meal_daily_limit",
        "category": "meals",
        "daily_limit": Decimal("100"),
        "per_claim_limit": Decimal("500"),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_non_tne_category_skips_amount_limits() -> None:
    """office_supplies has no T&E policy — high amount must not fail policy step."""
    extracted = {
        "expense_category": "office_supplies",
        "total_amount": "99999",
        "document_date": "2026-05-01",
    }
    policies = [_policy(name="meal_daily_limit", category="meals")]

    within, category, limit = check_expense_policy(
        extracted=extracted,
        policies=policies,
        submission_date=date(2026, 5, 10),
    )

    assert within is True
    assert category == "office_supplies"
    assert limit is None


def test_non_tne_category_still_checks_receipt_age() -> None:
    extracted = {
        "expense_category": "other",
        "total_amount": "10",
        "document_date": "2020-01-01",
    }

    within, category, limit = check_expense_policy(
        extracted=extracted,
        policies=[],
        submission_date=date(2026, 5, 10),
    )

    assert within is False
    assert category == "other"
    assert limit is None


def test_meals_category_enforces_per_claim_limit() -> None:
    extracted = {
        "expense_category": "meals",
        "total_amount": "600",
        "document_date": "2026-05-01",
    }
    policies = [
        _policy(daily_limit=None, per_claim_limit=Decimal("500")),
    ]

    within, category, limit = check_expense_policy(
        extracted=extracted,
        policies=policies,
        submission_date=date(2026, 5, 10),
    )

    assert within is False
    assert category == "meals"
    assert limit == Decimal("500")
