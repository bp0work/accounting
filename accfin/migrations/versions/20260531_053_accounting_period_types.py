"""accounting_period_types — period_type enum and audit_metadata JSONB."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260531_053"
down_revision = "20260531_052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE accounting_period_type AS ENUM ('monthly', 'audit', 'year_end');
        """
    )
    op.add_column(
        "accounting_periods",
        sa.Column(
            "period_type",
            postgresql.ENUM("monthly", "audit", "year_end", name="accounting_period_type", create_type=False),
            nullable=False,
            server_default="monthly",
        ),
    )
    op.add_column("accounting_periods", sa.Column("audit_metadata", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("accounting_periods", "audit_metadata")
    op.drop_column("accounting_periods", "period_type")
    op.execute("DROP TYPE IF EXISTS accounting_period_type;")
