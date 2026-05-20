"""create_expense_line_items_table — `19` §3.2."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260528_041"
down_revision = "20260528_040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE expense_category AS ENUM (
            'accommodation', 'airfare', 'ground_transport', 'meals',
            'entertainment', 'office_supplies', 'training', 'telecommunications',
            'professional_fees', 'other'
        );
        """
    )
    op.create_table(
        "expense_line_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "expense_claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense_claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(name="expense_category", create_type=False),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("merchant", sa.String(200), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="SGD"),
        sa.Column("amount_claimed", sa.Numeric(19, 4), nullable=False),
        sa.Column("amount_approved", sa.Numeric(19, 4), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("amount_sgd", sa.Numeric(19, 4), nullable=True),
        sa.Column(
            "receipt_attachment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("case_attachments.id"),
            nullable=True,
        ),
        sa.Column("policy_compliant", sa.Boolean(), nullable=True),
        sa.Column("policy_violation_note", sa.Text(), nullable=True),
        sa.Column(
            "gl_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coa_accounts.id"),
            nullable=True,
        ),
        sa.Column("cost_center", sa.String(50), nullable=True),
        sa.Column("project_code", sa.String(50), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.UniqueConstraint("expense_claim_id", "line_number", name="expense_line_items_claim_line_uq"),
        sa.CheckConstraint("amount_claimed > 0", name="expense_line_items_amount_check"),
    )
    op.create_index("expense_line_items_claim_id_idx", "expense_line_items", ["expense_claim_id"])
    op.create_index("expense_line_items_category_idx", "expense_line_items", ["category"])
    op.create_index("expense_line_items_date_idx", "expense_line_items", ["expense_date"])
    op.create_index("expense_line_items_gl_account_idx", "expense_line_items", ["gl_account_id"])
    op.execute(
        """
        CREATE TRIGGER expense_line_items_updated_at
        BEFORE UPDATE ON expense_line_items
        FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS expense_line_items_updated_at ON expense_line_items;")
    op.drop_index("expense_line_items_gl_account_idx", table_name="expense_line_items")
    op.drop_index("expense_line_items_date_idx", table_name="expense_line_items")
    op.drop_index("expense_line_items_category_idx", table_name="expense_line_items")
    op.drop_index("expense_line_items_claim_id_idx", table_name="expense_line_items")
    op.drop_table("expense_line_items")
    op.execute("DROP TYPE IF EXISTS expense_category;")
