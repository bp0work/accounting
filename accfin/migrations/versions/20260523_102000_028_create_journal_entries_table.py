"""create_journal_entries_table — `06` §11.1."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260523_028"
down_revision = "20260523_027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE journal_entry_status AS ENUM ('draft', 'pending', 'posted', 'reversed');
        """
    )
    je_status = postgresql.ENUM(name="journal_entry_status", create_type=False)

    op.create_table(
        "journal_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entry_number", sa.String(20), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_number", sa.String(20), nullable=True),
        sa.Column("status", je_status, nullable=False, server_default="draft"),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="SGD"),
        sa.Column("total_debit", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("total_credit", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("is_balanced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("posted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversal_of", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
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
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["reversal_of"], ["journal_entries.id"]),
        sa.UniqueConstraint("entry_number", name="journal_entries_entry_number_key"),
    )
    op.create_index("journal_entries_case_id_idx", "journal_entries", ["case_id"])
    op.create_index("journal_entries_status_idx", "journal_entries", ["status"])
    op.execute(
        """
        CREATE TRIGGER journal_entries_updated_at
            BEFORE UPDATE ON journal_entries
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.drop_table("journal_entries")
    op.execute("DROP TYPE IF EXISTS journal_entry_status;")
