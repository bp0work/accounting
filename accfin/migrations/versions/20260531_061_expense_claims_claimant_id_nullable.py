"""expense_claims.claimant_id nullable — email submissions without platform user."""

from alembic import op

revision = "20260531_061"
down_revision = "20260531_060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("expense_claims", "claimant_id", nullable=True)


def downgrade() -> None:
    op.alter_column("expense_claims", "claimant_id", nullable=False)
