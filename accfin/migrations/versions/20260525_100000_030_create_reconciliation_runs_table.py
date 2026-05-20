"""create_reconciliation_runs_table — `06` §12.1 (Phase 8 Treasury)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260525_030"
down_revision = "20260524_026b"
branch_labels = None
depends_on = None

reconciliation_status = postgresql.ENUM(
    "in_progress", "completed", "failed", name="reconciliation_status", create_type=False
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE reconciliation_status AS ENUM ('in_progress', 'completed', 'failed');
        """
    )
    op.create_table(
        "reconciliation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_period_from", sa.Date(), nullable=False),
        sa.Column("statement_period_to", sa.Date(), nullable=False),
        sa.Column("status", reconciliation_status, nullable=False, server_default="in_progress"),
        sa.Column("opening_balance", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("closing_balance", sa.Numeric(19, 4), nullable=True),
        sa.Column("statement_balance", sa.Numeric(19, 4), nullable=True),
        sa.Column("total_bank_transactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ledger_transactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmatched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual_matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("started_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "match_rules_used",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["coa_accounts.id"]),
        sa.ForeignKeyConstraint(["started_by"], ["users.id"]),
    )
    op.create_index("reconciliation_runs_account_idx", "reconciliation_runs", ["account_id"])
    op.create_index("reconciliation_runs_status_idx", "reconciliation_runs", ["status"])
    op.create_index(
        "reconciliation_runs_period_idx",
        "reconciliation_runs",
        ["statement_period_from", "statement_period_to"],
    )
    op.execute(
        """
        CREATE INDEX reconciliation_runs_account_period_idx
            ON reconciliation_runs(account_id, statement_period_from, statement_period_to);
        """
    )
    op.execute(
        """
        CREATE TRIGGER reconciliation_runs_updated_at
            BEFORE UPDATE ON reconciliation_runs
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.drop_table("reconciliation_runs")
    op.execute("DROP TYPE IF EXISTS reconciliation_status;")
