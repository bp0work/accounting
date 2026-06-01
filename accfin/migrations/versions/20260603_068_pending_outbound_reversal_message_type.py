"""pending_outbound reversal message_type check — `0.15.03a-reversal-message-type`."""

import sqlalchemy as sa
from alembic import op

revision = "20260603_068"
down_revision = "20260602_067"
branch_labels = None
depends_on = None

# Existing production values + approval/escalation mail types + expense reversal.
_MESSAGE_TYPES = (
    "clarification",
    "acknowledgement",
    "other",
    "approval_request",
    "approval_acknowledgement",
    "rejection_notification",
    "escalation_request",
    "clarification_request",
    "resubmission_request",
    "reversal_approval",
    "reversal_notification",
    "reversal_approved",
    "reversal_rejected",
)

_CHECK_NAME = "pending_outbound_emails_message_type_check"


def upgrade() -> None:
    quoted = ", ".join(f"'{v}'" for v in _MESSAGE_TYPES)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"ALTER TABLE pending_outbound_emails DROP CONSTRAINT IF EXISTS {_CHECK_NAME}"
        )
    )
    conn.execute(
        sa.text(
            f"ALTER TABLE pending_outbound_emails ADD CONSTRAINT {_CHECK_NAME} "
            f"CHECK (message_type IN ({quoted}))"
        )
    )


def downgrade() -> None:
    # Restore original migration 046 constraint (reversal types will fail if still in use).
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"ALTER TABLE pending_outbound_emails DROP CONSTRAINT IF EXISTS {_CHECK_NAME}"
        )
    )
    conn.execute(
        sa.text(
            f"ALTER TABLE pending_outbound_emails ADD CONSTRAINT {_CHECK_NAME} "
            "CHECK (message_type IN ('clarification', 'acknowledgement', 'other'))"
        )
    )
