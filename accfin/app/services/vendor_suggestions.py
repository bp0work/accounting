"""Merge counterparty and case-history vendor name suggestions."""

from __future__ import annotations

from sqlalchemy import distinct, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, Counterparty
from app.models.counterparty_master import CounterpartyAccount
from app.schemas.vendor_suggestion import VendorSuggestionResponse


def merge_vendor_suggestions(
    counterparties: list[tuple[str, str, str | None]],
    case_history_names: list[str],
    *,
    limit: int,
) -> list[VendorSuggestionResponse]:
    """Rank counterparty matches first, then case history; dedupe by name (case-insensitive)."""
    seen: set[str] = set()
    merged: list[VendorSuggestionResponse] = []

    def _append(entry: VendorSuggestionResponse) -> bool:
        key = entry.name.casefold()
        if not entry.name.strip() or key in seen:
            return len(merged) >= limit
        seen.add(key)
        merged.append(entry)
        return len(merged) >= limit

    for name, counterparty_type, email in counterparties:
        if _append(
            VendorSuggestionResponse(
                name=name,
                source="counterparty",
                counterparty_type=counterparty_type,
                email=email,
            )
        ):
            return merged

    for name in case_history_names:
        if _append(
            VendorSuggestionResponse(
                name=name,
                source="case_history",
                counterparty_type=None,
                email=None,
            )
        ):
            return merged

    return merged


async def search_counterparty_vendors(
    session: AsyncSession,
    search: str,
    *,
    limit: int,
) -> list[tuple[str, str, str | None]]:
    """Active counterparties: at least one active subaccount, or employee/staff master."""
    like = f"%{search.strip()}%"
    active_account = exists(
        select(1).where(
            CounterpartyAccount.counterparty_id == Counterparty.id,
            CounterpartyAccount.is_active.is_(True),
        )
    )
    stmt = (
        select(Counterparty.name, Counterparty.type, Counterparty.contact_email)
        .where(
            Counterparty.name.ilike(like),
            or_(
                Counterparty.type.in_(("employee", "staff")),
                active_account,
            ),
        )
        .order_by(Counterparty.name)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1], row[2]) for row in result.all()]


async def search_case_history_vendors(
    session: AsyncSession,
    search: str,
    *,
    limit: int,
) -> list[str]:
    like = f"%{search.strip()}%"
    vendor_expr = Case.workflow_metadata["extracted_fields"]["vendor_name"].astext
    stmt = (
        select(distinct(vendor_expr))
        .where(
            Case.type == "expense_claim",
            Case.status.in_(("posted", "reversed")),
            vendor_expr.isnot(None),
            vendor_expr != "",
            vendor_expr.ilike(like),
        )
        .order_by(vendor_expr)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all() if row[0]]


async def get_vendor_suggestions(
    session: AsyncSession,
    search: str,
    *,
    limit: int = 10,
) -> list[VendorSuggestionResponse]:
    counterparties = await search_counterparty_vendors(session, search, limit=limit)
    case_names = await search_case_history_vendors(session, search, limit=limit)
    return merge_vendor_suggestions(counterparties, case_names, limit=limit)
