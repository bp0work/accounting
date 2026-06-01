"""Foreign-currency GST conversion for expense journal posting."""

from decimal import Decimal

from workers.expense.handlers import _gst_amount_in_sgd


def test_gst_amount_in_sgd_converts_with_exchange_rate() -> None:
    extracted = {
        "currency": "USD",
        "tax_amount": "10",
        "exchange_rate": "1.35",
        "sgd_amount": "135",
    }
    assert _gst_amount_in_sgd(extracted) == Decimal("13.50")


def test_gst_amount_in_sgd_uses_persisted_sgd_tax() -> None:
    extracted = {
        "currency": "USD",
        "tax_amount": "10",
        "exchange_rate": "1.35",
        "sgd_tax": "13.50",
    }
    assert _gst_amount_in_sgd(extracted) == Decimal("13.50")


def test_gst_amount_in_sgd_sgd_currency_unchanged() -> None:
    extracted = {"currency": "SGD", "tax_amount": "9.00"}
    assert _gst_amount_in_sgd(extracted) == Decimal("9.00")
