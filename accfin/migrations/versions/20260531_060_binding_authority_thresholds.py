"""binding_authority_thresholds — seed Client Admin configurable approval tiers (`0.14.9`)."""

from alembic import op
import sqlalchemy as sa

revision = "20260531_060"
down_revision = "20260531_059"
branch_labels = None
depends_on = None

_THRESHOLDS = """
{
  "tier_1_ceiling": 3000,
  "tier_2_ceiling": 10000,
  "tier_3_threshold": 10000,
  "stp_confidence_minimum": 0.9,
  "tier_2_sla_hours": 4,
  "tier_3_sla_hours": 8
}
"""


def upgrade() -> None:
    conn = op.get_bind()
    for name in ("ap_approval_thresholds", "ar_approval_thresholds"):
        conn.execute(
            sa.text("""
            UPDATE policies
            SET rules = CAST(:rules AS jsonb),
                description = 'Binding authority approval thresholds (Client Admin)'
            WHERE name = :name AND is_active = true;
            """),
            {"name": name, "rules": _THRESHOLDS},
        )
    conn.execute(
        sa.text("""
        INSERT INTO policies (name, version, policy_type, description, rules, is_active)
        VALUES (
            'expense_approval_thresholds', 1, 'approval',
            'Binding authority thresholds for expense claims',
            CAST(:rules AS jsonb), true
        )
        ON CONFLICT (name, version) DO UPDATE SET
            rules = EXCLUDED.rules,
            description = EXCLUDED.description,
            is_active = true;
        """),
        {"rules": _THRESHOLDS},
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM policies WHERE name = 'expense_approval_thresholds' AND version = 1;")
    )
