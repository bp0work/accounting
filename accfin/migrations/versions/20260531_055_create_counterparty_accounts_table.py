"""payment_terms + counterparty_accounts — Phase 13 (`0.14.8`)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260531_055"
down_revision = "20260531_054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("due_days", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("discount_if_paid_within_days", sa.Integer(), nullable=True),
        sa.Column("minimum_invoice_amount", sa.Numeric(19, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("due_days >= 0", name="payment_terms_due_days_nonneg"),
    )
    op.create_table(
        "counterparty_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "counterparty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counterparty.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="bill_to"),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "payment_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_terms.id"),
            nullable=True,
        ),
        sa.Column("credit_limit_amount", sa.Numeric(19, 4), nullable=True),
        sa.Column("credit_limit_currency", sa.CHAR(3), server_default="SGD", nullable=True),
        sa.Column("counterparty_gst_reg", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("counterparty_id", "account_code", name="counterparty_accounts_parent_code_uq"),
        sa.CheckConstraint(
            "role IN ('bill_to', 'ship_to', 'remit_to', 'statement_to', 'other')",
            name="counterparty_accounts_role_chk",
        ),
    )
    op.create_index(
        "counterparty_accounts_parent_idx",
        "counterparty_accounts",
        ["counterparty_id"],
    )
    op.execute(
        """
        CREATE INDEX counterparty_accounts_active_idx
        ON counterparty_accounts (counterparty_id)
        WHERE is_active = TRUE;
        """
    )


def downgrade() -> None:
    op.drop_index("counterparty_accounts_active_idx", table_name="counterparty_accounts")
    op.drop_index("counterparty_accounts_parent_idx", table_name="counterparty_accounts")
    op.drop_table("counterparty_accounts")
    op.drop_table("payment_terms")
