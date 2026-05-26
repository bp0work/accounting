"""Binding authority tier evaluation — `0.14.9`."""

from decimal import Decimal

from app.policies.binding_authority import (
    BindingAuthorityThresholds,
    evaluate_approval_tier,
)


def _thresholds() -> BindingAuthorityThresholds:
    return BindingAuthorityThresholds.from_rules(None)


def test_tier1_stp_within_ceiling_and_confidence():
    th = _thresholds()
    assert (
        evaluate_approval_tier(
            amount=Decimal("2500"),
            confidence=0.95,
            risk_flags=[],
            thresholds=th,
        )
        == 1
    )


def test_tier2_above_tier1_ceiling():
    th = _thresholds()
    assert (
        evaluate_approval_tier(
            amount=Decimal("5000"),
            confidence=0.95,
            risk_flags=[],
            thresholds=th,
        )
        == 2
    )


def test_tier2_low_confidence_even_below_ceiling():
    th = _thresholds()
    assert (
        evaluate_approval_tier(
            amount=Decimal("1000"),
            confidence=0.5,
            risk_flags=[],
            thresholds=th,
        )
        == 2
    )


def test_tier3_at_threshold():
    th = _thresholds()
    assert (
        evaluate_approval_tier(
            amount=Decimal("10000"),
            confidence=0.99,
            risk_flags=[],
            thresholds=th,
        )
        == 3
    )


def test_tier3_blocking_risk_flag():
    th = _thresholds()
    assert (
        evaluate_approval_tier(
            amount=Decimal("100"),
            confidence=0.99,
            risk_flags=["high_risk"],
            thresholds=th,
        )
        == 3
    )
