"""create_email_attachments_table

Revision ID: 20260520_009
Revises: 20260520_008
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260520_009"
down_revision = "20260520_008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("wasabi_archive_path", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
            name="email_attachments_email_id_fkey",
            ondelete="CASCADE",
        ),
    )
    op.create_index("email_attachments_email_id_idx", "email_attachments", ["email_id"])
    op.create_index(
        "email_attachments_content_hash_idx", "email_attachments", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_table("email_attachments")
