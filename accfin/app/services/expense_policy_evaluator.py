"""Expense policy evaluation — `19` §5."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.expense import ExpenseLineItem, ExpensePolicy


@dataclass
class PolicyEvaluationResult:
    tier: int
    stp_eligible: bool
    violations: list[dict] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


def evaluate_expense_claim(
    *,
    line_items: list[ExpenseLineItem],
    total_claimed: Decimal,
    confidence: float,
    policies: list[ExpensePolicy],
    submission_date: date,
    claim_period_to: date,
    executive_threshold: Decimal = Decimal("5000"),
) -> PolicyEvaluationResult:
    violations: list[dict] = []
    risk_flags: list[str] = []
    tier = 1
    stp = confidence >= 0.90 and total_claimed > 0

    global_receipt = Decimal("50")
    global_approval = Decimal("500")
    for policy in policies:
        if not policy.is_active:
            continue
        if policy.applies_to_all_categories:
            global_receipt = min(global_receipt, policy.requires_receipt_above)
            global_approval = min(global_approval, policy.requires_approval_above)

    if (submission_date - claim_period_to).days > 30:
        risk_flags.append("late_submission")
        stp = False
        tier = max(tier, 2)

    for item in line_items:
        amount = item.amount_sgd or item.amount_claimed
        if amount > global_receipt and not item.receipt_attachment_id:
            risk_flags.append("receipt_missing")
            violations.append(
                {
                    "rule_name": "global_receipt_policy",
                    "line_item_id": str(item.id) if item.id else None,
                    "description": "Receipt required above threshold",
                    "severity": "high",
                }
            )
            stp = False
            tier = max(tier, 2)

        for policy in policies:
            if not policy.is_active:
                continue
            if policy.category and policy.category != item.category:
                continue
            if policy.daily_limit and amount > policy.daily_limit:
                risk_flags.append("amount_exceeds_daily_limit")
                violations.append(
                    {
                        "rule_name": policy.name,
                        "line_item_id": str(item.id) if item.id else None,
                        "description": f"Exceeds daily limit {policy.daily_limit}",
                        "severity": "medium",
                    }
                )
                stp = False
                tier = max(tier, 2)

    if total_claimed > global_approval:
        risk_flags.append("above_approval_threshold")
        stp = False
        tier = max(tier, 2)

    if total_claimed > executive_threshold:
        risk_flags.append("high_value_claim")
        stp = False
        tier = 3

    if confidence < 0.70:
        stp = False
        tier = max(tier, 2)

    if violations:
        stp = False

    return PolicyEvaluationResult(
        tier=tier,
        stp_eligible=stp,
        violations=violations,
        risk_flags=list(dict.fromkeys(risk_flags)),
    )
