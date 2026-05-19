"""disable_seed_admin_2fa_for_bootstrap

Revision ID: 20260520_007
Revises: 20260510_006d

Seed admins were inserted with two_factor_enabled=true but no secret.
Disable 2FA until setup flow completes (dev bootstrap).
"""

from alembic import op
import sqlalchemy as sa

revision = "20260520_007"
down_revision = "20260510_006d"
branch_labels = None
depends_on = None

SEED_USER_IDS = (
    "00000000-0000-0000-0000-000000000100",
    "00000000-0000-0000-0000-000000000101",
)


def upgrade() -> None:
    ids = ", ".join(f"'{uid}'" for uid in SEED_USER_IDS)
    op.execute(
        sa.text(f"""
        UPDATE users
        SET two_factor_enabled = false,
            two_factor_secret = NULL
        WHERE id IN ({ids});
        """)
    )


def downgrade() -> None:
    ids = ", ".join(f"'{uid}'" for uid in SEED_USER_IDS)
    op.execute(
        sa.text(f"""
        UPDATE users
        SET two_factor_enabled = true
        WHERE id IN ({ids});
        """)
    )
