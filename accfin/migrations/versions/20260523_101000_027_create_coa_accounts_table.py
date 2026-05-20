"""create_coa_accounts_table — `06` §10.1 (Phase 6 prerequisite for AR journals)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260523_027"
down_revision = "20260523_026c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE account_type AS ENUM ('asset', 'liability', 'equity', 'revenue', 'expense');"
    )
    account_type = postgresql.ENUM(name="account_type", create_type=False)

    op.create_table(
        "coa_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("account_type", account_type, nullable=False),
        sa.Column("account_subtype", sa.String(50), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_bank_account", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="SGD"),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["parent_id"], ["coa_accounts.id"]),
        sa.UniqueConstraint("account_code", name="coa_accounts_account_code_key"),
    )
    op.create_index("coa_accounts_code_idx", "coa_accounts", ["account_code"])
    op.create_index("coa_accounts_type_idx", "coa_accounts", ["account_type"])
    op.execute(
        """
        CREATE INDEX coa_accounts_active_idx ON coa_accounts(is_active) WHERE is_active = TRUE;
        """
    )
    op.execute(
        """
        CREATE TRIGGER coa_accounts_updated_at
            BEFORE UPDATE ON coa_accounts
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )

    op.execute(
        """
        INSERT INTO coa_accounts (account_code, account_name, account_type, is_bank_account) VALUES
            ('1200', 'Bank — DBS Operating', 'asset', true),
            ('1300', 'Accounts Receivable', 'asset', false),
            ('2100', 'GST Payable', 'liability', false),
            ('4100', 'Sales Revenue', 'revenue', false),
            ('5200', 'Discount Allowed', 'expense', false);
        """
    )


def downgrade() -> None:
    op.drop_table("coa_accounts")
    op.execute("DROP TYPE IF EXISTS account_type;")
