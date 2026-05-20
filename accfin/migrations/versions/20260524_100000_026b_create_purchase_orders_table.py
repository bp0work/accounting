"""create_purchase_orders_table — `06` §13a (Phase 7 AP Worker)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260524_026b"
down_revision = "20260523_029"
branch_labels = None
depends_on = None

po_status = postgresql.ENUM(
    "open", "partially_received", "fully_received", "cancelled", "closed",
    name="po_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE po_status AS ENUM (
            'open', 'partially_received', 'fully_received', 'cancelled', 'closed'
        );
        """
    )

    op.create_table(
        "purchase_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("po_number", sa.String(50), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", po_status, nullable=False, server_default="open"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="SGD"),
        sa.Column("total_amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("received_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("line_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparty.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("po_number", name="purchase_orders_po_number_key"),
    )
    op.create_index("purchase_orders_po_number_idx", "purchase_orders", ["po_number"])
    op.create_index("purchase_orders_counterparty_idx", "purchase_orders", ["counterparty_id"])
    op.execute(
        """
        CREATE INDEX purchase_orders_status_idx ON purchase_orders(status)
            WHERE status = 'open';
        """
    )
    op.create_index("purchase_orders_issue_date_idx", "purchase_orders", ["issue_date"])
    op.execute(
        """
        CREATE TRIGGER purchase_orders_updated_at
            BEFORE UPDATE ON purchase_orders
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )

    # AP GL accounts used by journal posting (`17` §5.1)
    op.execute(
        """
        INSERT INTO coa_accounts (account_code, account_name, account_type) VALUES
            ('2000', 'Trade Creditors', 'liability'),
            ('5500', 'Operating Expenses', 'expense'),
            ('1190', 'GST Input Tax', 'asset')
        ON CONFLICT (account_code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("purchase_orders")
    op.execute("DROP TYPE IF EXISTS po_status;")
