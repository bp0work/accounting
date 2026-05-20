"""create_counterparty_table — `06` §4.1."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260521_011"
down_revision = "20260520_010b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "counterparty",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("first_transaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_transaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
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
        sa.UniqueConstraint("code", name="counterparty_code_key"),
        sa.CheckConstraint(
            "type IN ('customer', 'supplier', 'employee', 'bank', 'other')",
            name="counterparty_type_check",
        ),
    )
    op.create_index("counterparty_type_idx", "counterparty", ["type"])
    op.execute(
        """
        CREATE INDEX counterparty_code_idx ON counterparty(code) WHERE code IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE TRIGGER counterparty_updated_at
            BEFORE UPDATE ON counterparty
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.drop_table("counterparty")
