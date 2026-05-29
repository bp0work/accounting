"""Expense validation helpers."""

from decimal import Decimal

from workers.common.expense_validation import (
    expense_parsing_missing,
    normalize_expense_category,
    receipt_validity_issues,
)


def test_normalize_expense_category_maps_transport() -> None:
    assert normalize_expense_category("transport") == "travel"


def test_parsing_missing_sender_validated() -> None:
    extracted = {
        "document_type": "receipt",
        "document_date": "2025-04-24",
        "merchant_name": "ACRA",
        "total_amount": "16.24",
        "currency": "SGD",
        "expense_category": "government_fees",
        "business_purpose": "Annual filing",
    }
    missing = expense_parsing_missing(extracted, sender_validated=False)
    assert "sender_validated" in missing


def test_receipt_older_than_90_days() -> None:
    from datetime import date, timedelta

    old = (date.today() - timedelta(days=120)).isoformat()
    issues = receipt_validity_issues(
        {
            "document_date": old,
            "total_amount": "10",
            "merchant_name": "Cafe",
        },
        today=date.today(),
    )
    assert "receipt_older_than_90_days" in issues
