"""reversal message types — reversal_approved, reversal_rejected on pending_outbound_emails."""

from alembic import op

revision = "20260603_070"
down_revision = "20260603_068"
branch_labels = None
depends_on = None

_MESSAGE_TYPES = (
    "clarification",
    "acknowledgement",
    "other",
    "reversal_approval",
    "reversal_notification",
    "reversal_approved",
    "reversal_rejected",
)


def _message_type_check(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"message_type = ANY (ARRAY[{quoted}]::text[])"


def upgrade() -> None:
    op.drop_constraint(
        "pending_outbound_emails_message_type_check",
        "pending_outbound_emails",
        type_="check",
    )
    op.create_check_constraint(
        "pending_outbound_emails_message_type_check",
        "pending_outbound_emails",
        _message_type_check(_MESSAGE_TYPES),
    )


def downgrade() -> None:
    op.drop_constraint(
        "pending_outbound_emails_message_type_check",
        "pending_outbound_emails",
        type_="check",
    )
    op.create_check_constraint(
        "pending_outbound_emails_message_type_check",
        "pending_outbound_emails",
        _message_type_check(
            (
                "clarification",
                "acknowledgement",
                "other",
                "reversal_approval",
                "reversal_notification",
            )
        ),
    )
