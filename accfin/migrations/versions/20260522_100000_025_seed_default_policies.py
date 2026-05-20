"""seed_default_policies — `10` §15 (adapted to Phase 4 policies schema)."""

from alembic import op

revision = "20260522_025"
down_revision = "20260521_017"
branch_labels = None
depends_on = None

_APPROVAL_RULES = """
[
  {
    "name": "high_value_approval",
    "priority": 10,
    "is_active": true,
    "conditions": {
      "field": "case.amount_value",
      "operator": "greater_than",
      "value": "50000"
    },
    "action": {"type": "require_approval", "tier": 3}
  },
  {
    "name": "medium_value_approval",
    "priority": 20,
    "is_active": true,
    "conditions": {
      "field": "case.amount_value",
      "operator": "greater_than",
      "value": "10000"
    },
    "action": {"type": "require_approval", "tier": 2}
  }
]
"""


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO policies (name, version, policy_type, description, rules, is_active)
        VALUES
            ('ap_approval_thresholds', 1, 'approval',
             'AP invoice approval tiers by amount', $rules${_APPROVAL_RULES}$rules$::jsonb, true),
            ('ar_approval_thresholds', 1, 'approval',
             'AR document approval tiers by amount', $rules${_APPROVAL_RULES}$rules$::jsonb, true),
            ('duplicate_detection_rules', 1, 'validation',
             'Duplicate invoice detection (scaffold)', '[]'::jsonb, true),
            ('gst_handling', 1, 'validation',
             'GST treatment rules (scaffold)', '[]'::jsonb, true)
        ON CONFLICT (name, version) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM policies
        WHERE name IN (
            'ap_approval_thresholds', 'ar_approval_thresholds',
            'duplicate_detection_rules', 'gst_handling'
        ) AND version = 1;
        """
    )
