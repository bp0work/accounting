"""create_mail_gateway_config_table

Revision ID: 20260520_010
Revises: 20260520_009
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260520_010"
down_revision = "20260520_009"
branch_labels = None
depends_on = None

case_type = postgresql.ENUM(name="case_type", create_type=False)


def upgrade() -> None:
    op.create_table(
        "mail_gateway_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("mailbox_mode", sa.String(30), nullable=False, server_default="executive_agent"),
        sa.Column("escalation_manager_email", sa.String(255), nullable=True),
        sa.Column(
            "requires_outbound_client_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("server_host", sa.String(255), nullable=False),
        sa.Column("server_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("use_ssl", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_case_type", case_type, nullable=True),
        sa.Column(
            "routing_rules",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("max_attachment_size_mb", sa.Integer(), nullable=False, server_default="25"),
        sa.Column(
            "allowed_attachment_types",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{application/pdf,image/png,image/jpeg}",
        ),
        sa.Column(
            "security_settings",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("email_address", name="mail_gateway_config_email_address_key"),
        sa.CheckConstraint(
            "mailbox_mode IN ('executive_agent', 'manager_human', 'notification_only')",
            name="mail_gateway_config_mailbox_mode_check",
        ),
    )
    op.create_index(
        "mail_gateway_config_active_idx",
        "mail_gateway_config",
        ["is_active"],
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index("mail_gateway_config_mode_idx", "mail_gateway_config", ["mailbox_mode"])


def downgrade() -> None:
    op.drop_table("mail_gateway_config")
