"""case_escalations + pending_outbound_emails — `06` §7.5–§7.6."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260529_046"
down_revision = "20260529_045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE case_escalation_status AS ENUM (
            'pending', 'approved', 'rejected', 'escalated', 'expired', 'cancelled'
        );
        """
    )
    op.execute(
        """
        CREATE TYPE pending_outbound_email_status AS ENUM (
            'awaiting_manager_approval', 'approved', 'sent', 'rejected', 'cancelled'
        );
        """
    )

    op.create_table(
        "case_escalations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column(
            "email_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("emails.id"),
            nullable=True,
        ),
        sa.Column(
            "originating_mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_gateway_config.id"),
            nullable=False,
        ),
        sa.Column(
            "target_mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_gateway_config.id"),
            nullable=True,
        ),
        sa.Column("target_email", sa.String(255), nullable=False),
        sa.Column(
            "parent_escalation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("case_escalations.id"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="case_escalation_status", create_type=False),
            nullable=False,
            server_default=sa.text("'pending'::case_escalation_status"),
        ),
        sa.Column("reason_code", sa.String(50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("manager_comment", sa.Text(), nullable=True),
        sa.Column("response_token_hash", sa.String(128), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_by_email", sa.String(255), nullable=True),
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
    )
    op.create_index("case_escalations_case_idx", "case_escalations", ["case_id"])
    op.execute(
        """
        CREATE INDEX case_escalations_status_idx ON case_escalations(status)
        WHERE status = 'pending';
        """
    )
    op.create_index("case_escalations_target_email_idx", "case_escalations", ["target_email"])
    op.create_index(
        "case_escalations_token_hash_idx", "case_escalations", ["response_token_hash"], unique=True
    )
    op.execute(
        """
        CREATE TRIGGER case_escalations_updated_at
        BEFORE UPDATE ON case_escalations
        FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )

    op.create_table(
        "pending_outbound_emails",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=True,
        ),
        sa.Column(
            "email_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("emails.id"),
            nullable=True,
        ),
        sa.Column(
            "mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_gateway_config.id"),
            nullable=False,
        ),
        sa.Column(
            "approver_mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_gateway_config.id"),
            nullable=True,
        ),
        sa.Column(
            "to_addresses",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "cc_addresses",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("subject", sa.String(998), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_plain", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(40), nullable=False, server_default="clarification"),
        sa.Column(
            "status",
            postgresql.ENUM(name="pending_outbound_email_status", create_type=False),
            nullable=False,
            server_default=sa.text(
                "'awaiting_manager_approval'::pending_outbound_email_status"
            ),
        ),
        sa.Column("rejection_reason_code", sa.String(50), nullable=True),
        sa.Column("manager_comment", sa.Text(), nullable=True),
        sa.Column("approved_by_email", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("smtp_message_id", sa.String(255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.CheckConstraint(
            "message_type IN ('clarification', 'acknowledgement', 'other')",
            name="pending_outbound_emails_message_type_check",
        ),
        sa.CheckConstraint(
            """rejection_reason_code IS NULL OR rejection_reason_code IN (
                'data_present_in_attachment', 'data_present_in_email',
                'parsing_incomplete', 'other'
            )""",
            name="pending_outbound_emails_rejection_reason_check",
        ),
    )
    op.execute(
        """
        CREATE INDEX pending_outbound_emails_status_idx ON pending_outbound_emails(status)
        WHERE status = 'awaiting_manager_approval';
        """
    )
    op.create_index("pending_outbound_emails_mailbox_idx", "pending_outbound_emails", ["mailbox_id"])
    op.create_index("pending_outbound_emails_case_idx", "pending_outbound_emails", ["case_id"])
    op.execute(
        """
        CREATE TRIGGER pending_outbound_emails_updated_at
        BEFORE UPDATE ON pending_outbound_emails
        FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pending_outbound_emails_updated_at ON pending_outbound_emails;")
    op.drop_index("pending_outbound_emails_case_idx", table_name="pending_outbound_emails")
    op.drop_index("pending_outbound_emails_mailbox_idx", table_name="pending_outbound_emails")
    op.execute("DROP INDEX IF EXISTS pending_outbound_emails_status_idx;")
    op.drop_table("pending_outbound_emails")

    op.execute("DROP TRIGGER IF EXISTS case_escalations_updated_at ON case_escalations;")
    op.drop_index("case_escalations_token_hash_idx", table_name="case_escalations")
    op.drop_index("case_escalations_target_email_idx", table_name="case_escalations")
    op.execute("DROP INDEX IF EXISTS case_escalations_status_idx;")
    op.drop_index("case_escalations_case_idx", table_name="case_escalations")
    op.drop_table("case_escalations")

    op.execute("DROP TYPE IF EXISTS pending_outbound_email_status;")
    op.execute("DROP TYPE IF EXISTS case_escalation_status;")
