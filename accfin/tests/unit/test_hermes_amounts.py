"""Unit tests — Hermes amount string normalization."""

from decimal import Decimal

from app.utils.hermes_amounts import clean_decimal_amount_string, decimal_from_hermes_amount


def test_clean_strips_currency_and_spaces() -> None:
    assert clean_decimal_amount_string("SGD 1,234.56") == "1234.56"
    assert clean_decimal_amount_string("$42.50") == "42.50"
    assert clean_decimal_amount_string("  99.00  ") == "99.00"


def test_clean_empty_defaults_to_zero() -> None:
    assert clean_decimal_amount_string(None) == "0"
    assert clean_decimal_amount_string("SGD —") == "0"


def test_decimal_from_hermes_amount() -> None:
    assert decimal_from_hermes_amount("EUR 12.34") == Decimal("12.34")
    assert decimal_from_hermes_amount("invalid", default="0") == Decimal("0")
