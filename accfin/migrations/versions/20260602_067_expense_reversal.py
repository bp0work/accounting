"""expense_reversal — pending_reversal_approval, reversed, reversal_rejected case statuses."""

import sqlalchemy as sa
from alembic import op

revision = "20260602_067"
down_revision = "20260601_066"
branch_labels = None
depends_on = None

_NEW_STATUSES = (
    "pending_reversal_approval",
    "reversed",
    "reversal_rejected",
)


def upgrade() -> None:
    conn = op.get_bind()
    for value in _NEW_STATUSES:
        conn.execute(sa.text(f"ALTER TYPE case_status ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
