"""AP workflow alignment — `0.14.11`.

Adds six new case_status values required by AP Process document,
payment_terms column on counterparty, and linked_case_id on emails
for gateway resubmission linking.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260527_062"
down_revision = "20260527_061"
branch_labels = None
depends_on = None

# New case_status ENUM values added in this migration
_NEW_STATUSES = [
    "validation",
    "case_rejected",
    "journal_entry_created",
    "journal_pending_approval",
    "journal_posted",
    "case_closed",
    "validation_completed",
]

_PAYMENT_TERMS_CONSTRAINT = (
    "payment_terms IN ('immediate','net_7','net_14','net_30','net_60','net_90')"
)


def upgrade() -> None:
    # 1. Extend case_status ENUM — each ADD VALUE is its own statement; PostgreSQL 12+
    #    allows this inside a transaction block.
    conn = op.get_bind()
    for value in _NEW_STATUSES:
        conn.execute(
            sa.text(f"ALTER TYPE case_status ADD VALUE IF NOT EXISTS '{value}'")
        )

    # 2. Add payment_terms to counterparty
    op.add_column(
        "counterparty",
        sa.Column("payment_terms", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "counterparty_payment_terms_chk",
        "counterparty",
        _PAYMENT_TERMS_CONSTRAINT,
    )

    # 3. Add linked_case_id to emails (resubmission FK — bare UUID, same pattern as
    #    emails.case_id; FK added separately to avoid ordering issues)
    op.add_column(
        "emails",
        sa.Column("linked_case_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "emails_linked_case_id_fkey",
        "emails",
        "cases",
        ["linked_case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_emails_linked_case_id", "emails", ["linked_case_id"])


def downgrade() -> None:
    op.drop_index("ix_emails_linked_case_id", table_name="emails")
    op.drop_constraint("emails_linked_case_id_fkey", "emails", type_="foreignkey")
    op.drop_column("emails", "linked_case_id")
    op.drop_constraint("counterparty_payment_terms_chk", "counterparty", type_="check")
    op.drop_column("counterparty", "payment_terms")
    # Note: PostgreSQL does not support DROP VALUE on ENUM types.
    # The new case_status values will remain; downgrade only removes schema additions.
