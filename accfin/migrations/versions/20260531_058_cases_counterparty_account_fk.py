"""cases.counterparty_account_id — Phase 13 (`0.14.8`)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260531_058"
down_revision = "20260531_057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column(
            "counterparty_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counterparty_accounts.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "cases_counterparty_account_idx",
        "cases",
        ["counterparty_account_id"],
    )


def downgrade() -> None:
    op.drop_index("cases_counterparty_account_idx", table_name="cases")
    op.drop_column("cases", "counterparty_account_id")
