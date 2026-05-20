"""create_expense_policies_table — `19` §3.3."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260528_042"
down_revision = "20260528_041"
branch_labels = None
depends_on = None

expense_category = postgresql.ENUM(name="expense_category", create_type=False)


def upgrade() -> None:
    op.create_table(
        "expense_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", expense_category, nullable=True),
        sa.Column(
            "applies_to_all_categories",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column(
            "applies_to_all_departments",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("daily_limit", sa.Numeric(19, 4), nullable=True),
        sa.Column("per_claim_limit", sa.Numeric(19, 4), nullable=True),
        sa.Column(
            "requires_receipt_above",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="50.00",
        ),
        sa.Column(
            "requires_approval_above",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="500.00",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "effective_from",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
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
    )
    op.create_index("expense_policies_category_idx", "expense_policies", ["category"])
    op.execute(
        """
        CREATE INDEX expense_policies_active_idx ON expense_policies(is_active)
        WHERE is_active = TRUE;
        """
    )
    op.create_index(
        "expense_policies_effective_idx", "expense_policies", ["effective_from", "effective_to"]
    )
    op.execute(
        """
        CREATE TRIGGER expense_policies_updated_at
        BEFORE UPDATE ON expense_policies
        FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS expense_policies_updated_at ON expense_policies;")
    op.drop_index("expense_policies_effective_idx", table_name="expense_policies")
    op.execute("DROP INDEX IF EXISTS expense_policies_active_idx;")
    op.drop_index("expense_policies_category_idx", table_name="expense_policies")
    op.drop_table("expense_policies")
