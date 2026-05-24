"""Detect travel-related expense claim line items."""

from __future__ import annotations

TRAVEL_CATEGORY_KEYWORDS = frozenset(
    {
        "flights",
        "flight",
        "airfare",
        "hotel",
        "accommodation",
        "transport",
        "taxi",
        "grab",
        "mileage",
        "ground_transport",
        "travel",
    }
)

TRAVEL_EXPENSE_CATEGORIES = frozenset(
    {"accommodation", "airfare", "ground_transport"}
)

NON_TRAVEL_HINTS = frozenset(
    {"meals", "office_supplies", "home office", "utilities", "home_office", "other"}
)


def is_travel_related_line_item(*, category: str | None, description: str | None) -> bool:
    cat = (category or "").lower().replace("_", " ")
    desc = (description or "").lower()
    combined = f"{cat} {desc}"
    if cat in TRAVEL_EXPENSE_CATEGORIES:
        return True
    return any(keyword in combined for keyword in TRAVEL_CATEGORY_KEYWORDS)


def claim_requires_travel_request(line_items) -> bool:
    """True when any line item is travel-related (meals/office/home office excluded)."""
    travel_found = False
    for item in line_items:
        cat = getattr(item, "category", None) or (
            item.get("category") if isinstance(item, dict) else None
        )
        desc = getattr(item, "description", None) or (
            item.get("description") if isinstance(item, dict) else None
        )
        cat_norm = (cat or "").lower()
        if cat_norm in NON_TRAVEL_HINTS and not any(
            k in (desc or "").lower() for k in ("flight", "hotel", "taxi", "grab", "mileage")
        ):
            continue
        if is_travel_related_line_item(category=cat, description=desc):
            travel_found = True
    return travel_found
