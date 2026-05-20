"""Rule-based bank/ledger matching — `17` §6.3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass
class MatchCandidate:
    bank_item_id: UUID
    ledger_item_id: UUID
    confidence: Decimal
    match_reason: str
    rule_name: str


def _norm_ref(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped.lower() if stripped else None


def _amounts_equal(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= Decimal("0.01")


def _amount_within_pct(a: Decimal, b: Decimal, pct: Decimal) -> bool:
    if a == 0 and b == 0:
        return True
    base = max(abs(a), abs(b), Decimal("0.01"))
    return abs(a - b) / base <= pct


def _date_within_days(d1: date, d2: date, days: int) -> bool:
    return abs((d1 - d2).days) <= days


def find_rule_based_matches(
    bank_items: list,
    ledger_items: list,
    *,
    amount_tolerance_pct: Decimal = Decimal("0.01"),
) -> list[MatchCandidate]:
    """Apply rules 1–4 in priority order; first winning rule per bank item."""
    matched_ledger: set[UUID] = set()
    results: list[MatchCandidate] = []

    for bank in bank_items:
        if bank.is_matched:
            continue
        ledgers = [l for l in ledger_items if not l.is_matched and l.id not in matched_ledger]
        candidate = _first_rule_match(bank, ledgers, amount_tolerance_pct)
        if candidate is None:
            continue
        ledger_id, conf, reason, rule_name = candidate
        results.append(
            MatchCandidate(
                bank_item_id=bank.id,
                ledger_item_id=ledger_id,
                confidence=conf,
                match_reason=reason,
                rule_name=rule_name,
            )
        )
        matched_ledger.add(ledger_id)

    return results


def _first_rule_match(
    bank, ledgers: list, amount_tolerance_pct: Decimal
) -> tuple[UUID, Decimal, str, str] | None:
    checks = (
        (_rule_exact_amount_date_reference, "exact_amount_date_reference", Decimal("1.00")),
        (_rule_exact_amount_tolerance_3days, "exact_amount_tolerance_3days", Decimal("0.95")),
        (_rule_exact_amount_date_no_reference, "exact_amount_date_no_reference", Decimal("0.85")),
    )
    for rule_fn, name, conf in checks:
        hits = rule_fn(bank, ledgers)
        if not hits:
            continue
        if len(hits) > 1 and name == "exact_amount_date_no_reference":
            return None
        return hits[0].id, conf, name, name

    hits = _rule_amount_tolerance_date(bank, ledgers, amount_tolerance_pct)
    if hits:
        return hits[0].id, Decimal("0.80"), "amount_within_tolerance", "amount_within_tolerance"
    return None


def _rule_exact_amount_date_reference(bank, ledgers: list) -> list:
    bref = _norm_ref(bank.reference)
    if not bref:
        return []
    return [
        ledger
        for ledger in ledgers
        if _norm_ref(ledger.reference) == bref
        and _amounts_equal(bank.amount, ledger.amount)
        and bank.transaction_date == ledger.transaction_date
    ]


def _rule_exact_amount_tolerance_3days(bank, ledgers: list) -> list:
    bref = _norm_ref(bank.reference)
    if not bref:
        return []
    return [
        ledger
        for ledger in ledgers
        if _norm_ref(ledger.reference) == bref
        and _amounts_equal(bank.amount, ledger.amount)
        and _date_within_days(bank.transaction_date, ledger.transaction_date, 3)
    ]


def _rule_exact_amount_date_no_reference(bank, ledgers: list) -> list:
    if _norm_ref(bank.reference):
        return []
    return [
        ledger
        for ledger in ledgers
        if not _norm_ref(ledger.reference)
        and _amounts_equal(bank.amount, ledger.amount)
        and bank.transaction_date == ledger.transaction_date
    ]


def _rule_amount_tolerance_date(bank, ledgers: list, pct: Decimal) -> list:
    return [
        ledger
        for ledger in ledgers
        if _amount_within_pct(bank.amount, ledger.amount, pct)
        and _date_within_days(bank.transaction_date, ledger.transaction_date, 3)
    ]
