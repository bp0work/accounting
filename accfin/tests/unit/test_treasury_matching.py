"""Treasury rule-based matching — `17` §6.3."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from workers.treasury.matching import find_rule_based_matches


def _bank(amount: str, ref: str, tx_date: date):
    return SimpleNamespace(
        id=uuid4(),
        amount=Decimal(amount),
        reference=ref,
        transaction_date=tx_date,
        is_matched=False,
    )


def _ledger(amount: str, ref: str, tx_date: date):
    return SimpleNamespace(
        id=uuid4(),
        amount=Decimal(amount),
        reference=ref,
        transaction_date=tx_date,
        is_matched=False,
    )


def test_rule1_exact_amount_date_reference():
    d = date(2026, 4, 15)
    bank = _bank("100.00", "TT-001", d)
    ledger = _ledger("100.00", "TT-001", d)
    matches = find_rule_based_matches([bank], [ledger])
    assert len(matches) == 1
    assert matches[0].match_reason == "exact_amount_date_reference"
    assert matches[0].confidence == Decimal("1.00")


def test_rule3_ambiguous_skipped():
    d = date(2026, 4, 16)
    bank = _bank("250.00", None, d)
    ledgers = [_ledger("250.00", None, d), _ledger("250.00", None, d)]
    matches = find_rule_based_matches([bank], ledgers)
    assert matches == []


def test_rule2_date_tolerance():
    bank = _bank("500.00", "REF-A", date(2026, 4, 10))
    ledger = _ledger("500.00", "REF-A", date(2026, 4, 12))
    matches = find_rule_based_matches([bank], [ledger])
    assert len(matches) == 1
    assert matches[0].match_reason == "exact_amount_tolerance_3days"
