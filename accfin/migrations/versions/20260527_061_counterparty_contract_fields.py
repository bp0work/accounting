"""counterparty contract fields — `0.14.10`.

Add vendor contract metadata fields to `counterparty`.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260527_061"
down_revision = "20260531_060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "counterparty",
        sa.Column("has_contract", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("counterparty", sa.Column("contract_reference", sa.String(length=255), nullable=True))
    op.add_column("counterparty", sa.Column("contract_start_date", sa.Date(), nullable=True))
    op.add_column("counterparty", sa.Column("contract_expiry_date", sa.Date(), nullable=True))
    op.add_column("counterparty", sa.Column("supplier_owner", sa.Text(), nullable=True))
    op.add_column(
        "counterparty",
        sa.Column(
            "contract_warning_days", sa.Integer(), nullable=False, server_default=sa.text("30")
        ),
    )


def downgrade() -> None:
    op.drop_column("counterparty", "contract_warning_days")
    op.drop_column("counterparty", "supplier_owner")
    op.drop_column("counterparty", "contract_expiry_date")
    op.drop_column("counterparty", "contract_start_date")
    op.drop_column("counterparty", "contract_reference")
    op.drop_column("counterparty", "has_contract")

