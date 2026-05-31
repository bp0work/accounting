"""Expense validation helpers."""

from decimal import Decimal

from workers.common.expense_validation import (
    PARSING_MANDATORY_FIELDS,
    PARSING_OPTIONAL_FIELDS,
    expense_parsing_missing,
    normalize_expense_category,
    receipt_validity_issues,
)


def test_normalize_expense_category_maps_transport() -> None:
    assert normalize_expense_category("transport") == "travel"


def test_parsing_missing_ignores_sender_validated_and_business_purpose() -> None:
    extracted = {
        "document_type": "receipt",
        "document_date": "2025-04-24",
        "vendor_name": "ACRA",
        "total_amount": "16.24",
        "currency": "SGD",
        "expense_category": "government_fees",
    }
    missing = expense_parsing_missing(extracted)
    assert "sender_validated" not in missing
    assert "business_purpose" not in missing
    assert missing == []


def test_parsing_missing_required_fields() -> None:
    missing = expense_parsing_missing({"document_type": "receipt"})
    assert set(missing) == set(PARSING_MANDATORY_FIELDS) - {"document_type"}


def test_parsing_optional_fields_tuple() -> None:
    assert "business_purpose" in PARSING_OPTIONAL_FIELDS


def test_receipt_older_than_90_days() -> None:
    from datetime import date, timedelta

    old = (date.today() - timedelta(days=120)).isoformat()
    issues = receipt_validity_issues(
        {
            "document_date": old,
            "total_amount": "10",
            "vendor_name": "Cafe",
        },
        today=date.today(),
    )
    assert "receipt_older_than_90_days" in issues
