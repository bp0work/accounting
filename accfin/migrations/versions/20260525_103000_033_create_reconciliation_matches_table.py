"""create_reconciliation_matches_table — `06` §12.4."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260525_033"
down_revision = "20260525_032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("match_reason", sa.String(100), nullable=True),
        sa.Column("matched_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("is_voided", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"], ["reconciliation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["bank_item_id"], ["reconciliation_bank_items.id"]),
        sa.ForeignKeyConstraint(["ledger_item_id"], ["reconciliation_ledger_items.id"]),
        sa.ForeignKeyConstraint(["matched_by"], ["users.id"]),
        sa.CheckConstraint(
            "match_type IN ('auto', 'manual')", name="reconciliation_matches_match_type_check"
        ),
    )
    op.create_index(
        "reconciliation_matches_run_id_idx",
        "reconciliation_matches",
        ["reconciliation_run_id"],
    )
    op.create_index(
        "reconciliation_matches_bank_item_idx",
        "reconciliation_matches",
        ["bank_item_id"],
    )
    op.create_index(
        "reconciliation_matches_ledger_item_idx",
        "reconciliation_matches",
        ["ledger_item_id"],
    )


def downgrade() -> None:
    op.drop_table("reconciliation_matches")
