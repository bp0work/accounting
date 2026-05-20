"""create_reconciliation_bank_items_table — `06` §12.2."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260525_031"
down_revision = "20260525_030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_bank_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="SGD"),
        sa.Column("is_matched", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("match_type", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"], ["reconciliation_runs.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint("match_type IN ('auto', 'manual')", name="reconciliation_bank_items_match_type_check"),
    )
    op.create_index(
        "reconciliation_bank_items_run_idx",
        "reconciliation_bank_items",
        ["reconciliation_run_id"],
    )


def downgrade() -> None:
    op.drop_table("reconciliation_bank_items")
