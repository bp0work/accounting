"""Expense category normalization and GL code mapping."""

from __future__ import annotations

EXPENSE_CATEGORIES = frozenset(
    {
        "meals",
        "travel",
        "transport",
        "accommodation",
        "office_supplies",
        "government_fees",
        "entertainment",
        "other",
    }
)

# Preferred GL codes by category (tenant may configure accounts with these codes).
CATEGORY_EXPENSE_ACCOUNT_CODES: dict[str, str] = {
    "meals": "5100",
    "entertainment": "5100",
    "travel": "5200",
    "transport": "5200",
    "accommodation": "5300",
    "office_supplies": "5400",
    "government_fees": "5500",
    "other": "5590",
}


def normalize_expense_category(raw: str | None) -> str:
    if not raw:
        return "other"
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if key == "transport":
        return "travel"
    if key in EXPENSE_CATEGORIES:
        return key
    return "other"
