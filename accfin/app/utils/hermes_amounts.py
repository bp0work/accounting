"""Normalize monetary strings from Hermes / LLM extraction before Decimal conversion."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NON_DECIMAL_CHARS = re.compile(r"[^\d.]")


def clean_decimal_amount_string(val: object | None, *, default: str = "0") -> str:
    """Strip currency symbols, spaces, and commas; keep digits and decimal point."""
    cleaned = _NON_DECIMAL_CHARS.sub("", str(val if val is not None else default))
    if not cleaned:
        return default
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = parts[0] + "." + "".join(parts[1:])
    return cleaned or default


def decimal_from_hermes_amount(val: object | None, *, default: str = "0") -> Decimal:
    """Parse a Hermes amount field to Decimal after ``clean_decimal_amount_string``."""
    try:
        return Decimal(clean_decimal_amount_string(val, default=default))
    except InvalidOperation:
        return Decimal(default)
