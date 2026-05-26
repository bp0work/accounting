"""Binding authority tier evaluation — `10` §7, `0.14.9`."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

BINDING_AUTHORITY_REASON_PREFIX = "BINDING_AUTHORITY"

CASE_TYPE_POLICY_NAMES: dict[str, str] = {
    "ap_invoice": "ap_approval_thresholds",
    "ap_po_validation": "ap_approval_thresholds",
    "ap_payment_proposal": "ap_approval_thresholds",
    "ar_invoice": "ar_approval_thresholds",
    "ar_credit_note": "ar_approval_thresholds",
    "ar_payment_advice": "ar_approval_thresholds",
    "expense_claim": "expense_approval_thresholds",
}

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "tier_1_ceiling": 3000,
    "tier_2_ceiling": 10000,
    "tier_3_threshold": 10000,
    "stp_confidence_minimum": 0.9,
    "tier_2_sla_hours": 4,
    "tier_3_sla_hours": 8,
}

BLOCKING_RISK_FLAGS = frozenset(
    {
        "high_risk",
        "high_value_transaction",
        "duplicate_suspected",
        "policy_override_requested",
    }
)


@dataclass(frozen=True)
class BindingAuthorityThresholds:
    tier_1_ceiling: Decimal
    tier_2_ceiling: Decimal
    tier_3_threshold: Decimal
    stp_confidence_minimum: float
    tier_2_sla_hours: int
    tier_3_sla_hours: int

    @classmethod
    def from_rules(cls, rules: dict[str, Any] | list | None) -> BindingAuthorityThresholds:
        data = rules if isinstance(rules, dict) else {}
        return cls(
            tier_1_ceiling=Decimal(str(data.get("tier_1_ceiling", DEFAULT_THRESHOLDS["tier_1_ceiling"]))),
            tier_2_ceiling=Decimal(str(data.get("tier_2_ceiling", DEFAULT_THRESHOLDS["tier_2_ceiling"]))),
            tier_3_threshold=Decimal(
                str(data.get("tier_3_threshold", DEFAULT_THRESHOLDS["tier_3_threshold"]))
            ),
            stp_confidence_minimum=float(
                data.get("stp_confidence_minimum", DEFAULT_THRESHOLDS["stp_confidence_minimum"])
            ),
            tier_2_sla_hours=int(data.get("tier_2_sla_hours", DEFAULT_THRESHOLDS["tier_2_sla_hours"])),
            tier_3_sla_hours=int(data.get("tier_3_sla_hours", DEFAULT_THRESHOLDS["tier_3_sla_hours"])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier_1_ceiling": float(self.tier_1_ceiling),
            "tier_2_ceiling": float(self.tier_2_ceiling),
            "tier_3_threshold": float(self.tier_3_threshold),
            "stp_confidence_minimum": self.stp_confidence_minimum,
            "tier_2_sla_hours": self.tier_2_sla_hours,
            "tier_3_sla_hours": self.tier_3_sla_hours,
        }


def policy_name_for_case_type(case_type: str) -> str | None:
    return CASE_TYPE_POLICY_NAMES.get(case_type)


def evaluate_approval_tier(
    *,
    amount: Decimal | float,
    confidence: float,
    risk_flags: list[str] | None,
    thresholds: BindingAuthorityThresholds,
) -> int:
    """Return approval tier 1 (STP), 2 (Accounts Manager), or 3 (CFO)."""
    amt = Decimal(str(amount))
    flags = set(risk_flags or [])
    if flags & BLOCKING_RISK_FLAGS:
        return 3
    if amt >= thresholds.tier_3_threshold:
        return 3
    if (
        amt <= thresholds.tier_1_ceiling
        and confidence >= thresholds.stp_confidence_minimum
        and not flags
    ):
        return 1
    return 2


def sla_hours_for_tier(tier: int, thresholds: BindingAuthorityThresholds) -> int:
    if tier >= 3:
        return thresholds.tier_3_sla_hours
    if tier == 2:
        return thresholds.tier_2_sla_hours
    return 0
