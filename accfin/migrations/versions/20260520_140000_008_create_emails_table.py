"""create_emails_table

Revision ID: 20260520_008
Revises: 20260520_007

Phase 3 — `06` §7.1. Creates email_status and case_type enums (case_type reused in Phase 4).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260520_008"
down_revision = "20260520_007"
branch_labels = None
depends_on = None

email_status = postgresql.ENUM(
    "received",
    "parsed",
    "classified",
    "queued",
    "processed",
    "failed",
    "duplicate",
    "ignored",
    name="email_status",
    create_type=False,
)

case_type = postgresql.ENUM(
    "ar_invoice",
    "ar_payment_advice",
    "ar_credit_note",
    "ap_invoice",
    "ap_po_validation",
    "ap_payment_proposal",
    "treasury_reconciliation",
    "treasury_fx",
    "treasury_suspense",
    "general_inquiry",
    name="case_type",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE email_status AS ENUM (
            'received', 'parsed', 'classified', 'queued', 'processed',
            'failed', 'duplicate', 'ignored'
        );
        """
    )
    op.execute(
        """
        CREATE TYPE case_type AS ENUM (
            'ar_invoice', 'ar_payment_advice', 'ar_credit_note',
            'ap_invoice', 'ap_po_validation', 'ap_payment_proposal',
            'treasury_reconciliation', 'treasury_fx', 'treasury_suspense',
            'general_inquiry'
        );
        """
    )

    op.create_table(
        "emails",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("message_id", sa.String(500), nullable=False),
        sa.Column("mailbox_address", sa.String(255), nullable=False),
        sa.Column("from_address", sa.String(255), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column(
            "to_addresses",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "cc_addresses",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("body_preview", sa.String(500), nullable=True),
        sa.Column(
            "status",
            email_status,
            nullable=False,
            server_default=sa.text("'received'::email_status"),
        ),
        sa.Column("classified_as", case_type, nullable=True),
        sa.Column("classification_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("spf_result", sa.String(20), nullable=True),
        sa.Column("dkim_result", sa.String(20), nullable=True),
        sa.Column("dmarc_result", sa.String(20), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_number", sa.String(20), nullable=True),
        sa.Column(
            "processing_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("message_id", name="emails_message_id_key"),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["emails.id"], name="emails_duplicate_of_id_fkey"),
        sa.CheckConstraint(
            "spf_result IS NULL OR spf_result IN ('pass', 'fail', 'neutral', 'none')",
            name="emails_spf_result_check",
        ),
        sa.CheckConstraint(
            "dkim_result IS NULL OR dkim_result IN ('pass', 'fail', 'neutral', 'none')",
            name="emails_dkim_result_check",
        ),
        sa.CheckConstraint(
            "dmarc_result IS NULL OR dmarc_result IN ('pass', 'fail', 'neutral', 'none')",
            name="emails_dmarc_result_check",
        ),
    )

    op.create_index("emails_message_id_idx", "emails", ["message_id"])
    op.create_index("emails_status_idx", "emails", ["status"])
    op.create_index("emails_from_address_idx", "emails", ["from_address"])
    op.create_index("emails_case_id_idx", "emails", ["case_id"])
    op.create_index("emails_received_at_idx", "emails", ["received_at"])
    op.create_index("emails_content_hash_idx", "emails", ["content_hash"])
    op.create_index(
        "emails_duplicate_idx",
        "emails",
        ["is_duplicate"],
        postgresql_where=sa.text("is_duplicate = TRUE"),
    )
    op.create_index("emails_classified_as_idx", "emails", ["classified_as"])
    op.create_index("emails_mailbox_status_idx", "emails", ["mailbox_address", "status"])


def downgrade() -> None:
    op.drop_table("emails")
    op.execute("DROP TYPE IF EXISTS case_type;")
    op.execute("DROP TYPE IF EXISTS email_status;")
