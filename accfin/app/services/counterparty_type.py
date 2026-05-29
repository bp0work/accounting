"""Counterparty type normalization — API/UI vs database check constraint."""

from __future__ import annotations

from fastapi import status

from app.core.exceptions import AppHTTPException

# `counterparty_type_check` in migration `011` — allows supplier, not vendor.
_COUNTERPARTY_DB_TYPES = frozenset(
    {"customer", "supplier", "employee", "bank", "other", "staff"}
)


def normalize_counterparty_type(type_value: str) -> str:
    """Map API/UI alias ``vendor`` to DB value ``supplier``."""
    normalized = type_value.strip().lower()
    if normalized == "vendor":
        return "supplier"
    if normalized not in _COUNTERPARTY_DB_TYPES:
        raise AppHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_COUNTERPARTY_TYPE",
            message=(
                f"Invalid counterparty type '{type_value}'. "
                "Allowed: customer, vendor, supplier, employee, staff, bank, other."
            ),
        )
    return normalized
