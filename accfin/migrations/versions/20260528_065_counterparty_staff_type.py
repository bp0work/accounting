"""counterparty staff type — `0.14.45-expense-workflow`.

Adds ``staff`` to counterparty type check (contact_email already on counterparty).
"""

from alembic import op

revision = "20260528_065"
down_revision = "20260528_064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("counterparty_type_check", "counterparty", type_="check")
    op.create_check_constraint(
        "counterparty_type_check",
        "counterparty",
        "type IN ('customer', 'supplier', 'employee', 'bank', 'other', 'staff')",
    )


def downgrade() -> None:
    op.drop_constraint("counterparty_type_check", "counterparty", type_="check")
    op.create_check_constraint(
        "counterparty_type_check",
        "counterparty",
        "type IN ('customer', 'supplier', 'employee', 'bank', 'other')",
    )
