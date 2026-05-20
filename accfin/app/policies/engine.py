"""Policy condition evaluation scaffold — `10` §16."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any


class ConditionEvaluator:
    """Evaluates policy conditions against a case context (pure, no I/O)."""

    def evaluate(self, condition: dict, context: dict) -> bool:
        operator = condition.get("operator")
        if operator == "AND":
            return all(self.evaluate(c, context) for c in condition.get("conditions", []))
        if operator == "OR":
            return any(self.evaluate(c, context) for c in condition.get("conditions", []))
        if operator == "NOT":
            nested = condition.get("conditions", [])
            if not nested:
                return False
            return not self.evaluate(nested[0], context)
        return self._evaluate_simple(condition, context)

    def _evaluate_simple(self, condition: dict, context: dict) -> bool:
        operator = condition["operator"]
        actual = self._resolve_field(condition["field"], context)
        expected = condition.get("value")

        if actual is None:
            if operator == "is_empty":
                return True
            if operator == "is_not_empty":
                return False
            if operator == "equals" and expected is None:
                return True
            return False

        if operator in (
            "greater_than",
            "greater_than_or_equal",
            "less_than",
            "less_than_or_equal",
            "between",
        ) and isinstance(expected, str):
            expected = Decimal(expected)
            actual = Decimal(str(actual))

        evaluators = {
            "equals": lambda a, e: a == e,
            "not_equals": lambda a, e: a != e,
            "greater_than": lambda a, e: a > e,
            "greater_than_or_equal": lambda a, e: a >= e,
            "less_than": lambda a, e: a < e,
            "less_than_or_equal": lambda a, e: a <= e,
            "between": lambda a, e: e[0] <= a <= e[1],
            "contains": lambda a, e: e in (a or []),
            "not_contains": lambda a, e: e not in (a or []),
            "is_empty": lambda a, _: not bool(a),
            "is_not_empty": lambda a, _: bool(a),
            "in": lambda a, e: a in e,
            "starts_with": lambda a, e: str(a).startswith(str(e)),
            "ends_with": lambda a, e: str(a).endswith(str(e)),
            "matches_regex": lambda a, e: bool(re.match(e, str(a))),
        }
        fn = evaluators.get(operator)
        if fn is None:
            raise ValueError(f"Unknown operator: {operator}")
        return bool(fn(actual, expected))

    def _resolve_field(self, field_path: str, context: dict) -> Any:
        current: Any = context
        for part in field_path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


class PolicyEngine:
    def __init__(self, condition_evaluator: ConditionEvaluator | None = None) -> None:
        self.evaluator = condition_evaluator or ConditionEvaluator()
        self._action_rank = {
            "reject": 1,
            "escalate_review": 2,
            "require_approval": 3,
            "require_document": 4,
            "flag_risk": 5,
            "auto_release": 6,
        }

    def evaluate_policy(self, policy: dict, context: dict) -> dict:
        rules = sorted(
            [r for r in policy.get("rules", []) if r.get("is_active", True)],
            key=lambda r: r.get("priority", 100),
        )
        for rule in rules:
            try:
                if self.evaluator.evaluate(rule.get("conditions", {}), context):
                    return {
                        "matched": True,
                        "matched_rule": rule,
                        "action": rule["action"],
                        "reason": f"Matched rule: {rule.get('name', 'unknown')}",
                    }
            except Exception:
                continue
        return {
            "matched": False,
            "matched_rule": None,
            "action": policy.get(
                "default_action",
                {
                    "type": "require_approval",
                    "tier": 2,
                    "reason": "No matching rule — default approval required",
                },
            ),
            "reason": "No rule matched — using default action",
        }

    def combine_results(self, results: list[dict]) -> dict:
        if not results:
            return {"type": "require_approval", "tier": 2, "reason": "No policies evaluated"}

        def action_rank(result: dict) -> int:
            action = result.get("action", {})
            base = self._action_rank.get(action.get("type"), 99)
            if action.get("type") == "require_approval":
                tier = int(action.get("tier", 2))
                return base * 10 + (4 - tier)
            return base * 10

        most_restrictive = min(results, key=action_rank)
        all_flags: set[str] = set()
        for r in results:
            all_flags.update(r.get("action", {}).get("risk_flags", []))
        combined = dict(most_restrictive["action"])
        combined["risk_flags"] = sorted(all_flags)
        return combined
