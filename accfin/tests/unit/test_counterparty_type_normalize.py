"""Unit tests — counterparty type vendor → supplier normalization."""

import pytest

from app.services.counterparty_type import normalize_counterparty_type as _normalize_counterparty_type
from app.core.exceptions import AppHTTPException


def test_vendor_maps_to_supplier():
    assert _normalize_counterparty_type("vendor") == "supplier"
    assert _normalize_counterparty_type("Vendor") == "supplier"


def test_other_types_unchanged():
    assert _normalize_counterparty_type("customer") == "customer"
    assert _normalize_counterparty_type("supplier") == "supplier"


def test_invalid_type_raises():
    with pytest.raises(AppHTTPException) as exc_info:
        _normalize_counterparty_type("invalid")
    assert exc_info.value.status_code == 422
