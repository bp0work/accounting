"""Ensure reversal_approved and reversal_rejected in outbound message_type check.

Idempotent re-apply of migration 068 constraint — safe when 068 already ran without
the full reversal type list. Revision 068 file is the canonical definition; this
revision guarantees deployed databases pick up reversal_approved / reversal_rejected.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260603_069"
down_revision = "20260603_068"
branch_labels = None
depends_on = None

# Keep in sync with 20260603_068_pending_outbound_reversal_message_type.py
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
    # Match migration 068 downgrade.
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
