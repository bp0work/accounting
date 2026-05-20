"""Policy engine operator matrix — `10` §16."""

from app.policies.engine import ConditionEvaluator, PolicyEngine


def test_greater_than_amount():
    ev = ConditionEvaluator()
    assert ev.evaluate(
        {"field": "case.amount_value", "operator": "greater_than", "value": "1000"},
        {"case": {"amount_value": 5000}},
    )


def test_and_compound():
    ev = ConditionEvaluator()
    condition = {
        "operator": "AND",
        "conditions": [
            {"field": "case.type", "operator": "equals", "value": "ap_invoice"},
            {"field": "case.amount_value", "operator": "greater_than", "value": "10000"},
        ],
    }
    assert ev.evaluate(condition, {"case": {"type": "ap_invoice", "amount_value": 15000}})


def test_policy_engine_matches_rule():
    engine = PolicyEngine()
    policy = {
        "rules": [
            {
                "name": "high_value",
                "priority": 1,
                "is_active": True,
                "conditions": {
                    "field": "case.amount_value",
                    "operator": "greater_than",
                    "value": "50000",
                },
                "action": {"type": "require_approval", "tier": 3},
            }
        ],
        "default_action": {"type": "require_approval", "tier": 2},
    }
    result = engine.evaluate_policy(policy, {"case": {"amount_value": 75000}})
    assert result["matched"]
    assert result["action"]["tier"] == 3


def test_combine_most_restrictive():
    engine = PolicyEngine()
    results = [
        {"action": {"type": "require_approval", "tier": 2}},
        {"action": {"type": "require_approval", "tier": 3}},
    ]
    combined = engine.combine_results(results)
    assert combined["tier"] == 3
