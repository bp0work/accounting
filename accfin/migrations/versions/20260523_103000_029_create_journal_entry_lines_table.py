"""create_journal_entry_lines_table — `06` §11.2."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260523_029"
down_revision = "20260523_028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_entry_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("debit", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("cost_center", sa.String(50), nullable=True),
        sa.Column("project_code", sa.String(50), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["coa_accounts.id"]),
        sa.UniqueConstraint(
            "journal_entry_id", "line_number", name="journal_entry_lines_entry_line_key"
        ),
        sa.CheckConstraint("debit >= 0", name="journal_entry_lines_debit_check"),
        sa.CheckConstraint("credit >= 0", name="journal_entry_lines_credit_check"),
    )
    op.create_index(
        "journal_entry_lines_entry_id_idx", "journal_entry_lines", ["journal_entry_id"]
    )
    op.create_index(
        "journal_entry_lines_account_id_idx", "journal_entry_lines", ["account_id"]
    )


def downgrade() -> None:
    op.drop_table("journal_entry_lines")
