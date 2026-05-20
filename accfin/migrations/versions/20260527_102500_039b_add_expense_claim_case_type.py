"""add_expense_claim_case_type — `05` §5.3, `16` §10 Phase 11 enum prep."""

from alembic import op

revision = "20260527_039b"
down_revision = "20260527_039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE case_type ADD VALUE IF NOT EXISTS 'expense_claim';")


def downgrade() -> None:
    pass
