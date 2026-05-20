"""finance_activity_log + SOP seeds — `06` §7.4, `17` §10.7."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260529_045"
down_revision = "20260528_044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_activity_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "business_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("(CURRENT_DATE AT TIME ZONE 'Asia/Singapore')::date"),
        ),
        sa.Column(
            "mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_gateway_config.id"),
            nullable=True,
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
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_name", sa.String(100), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
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
        sa.CheckConstraint(
            "actor_type IN ('worker', 'manager', 'human', 'system')",
            name="finance_activity_log_actor_type_check",
        ),
    )
    op.create_index("finance_activity_log_occurred_idx", "finance_activity_log", ["occurred_at"])
    op.create_index(
        "finance_activity_log_business_date_idx", "finance_activity_log", ["business_date"]
    )
    op.create_index("finance_activity_log_mailbox_idx", "finance_activity_log", ["mailbox_id"])
    op.create_index("finance_activity_log_case_idx", "finance_activity_log", ["case_id"])

    op.execute(
        """
        UPDATE mail_gateway_config SET requires_outbound_client_approval = true
        WHERE email_address IN ('accar.mmlogistix@bp0.work', 'acc.mmlogistix@bp0.work',
            'fin.mmlogistix@bp0.work', 'cfo.mmlogistix@bp0.work', 'ceo.mmlogistix@bp0.work');
        UPDATE mail_gateway_config SET requires_outbound_client_approval = false
        WHERE email_address IN ('accap.mmlogistix@bp0.work', 'accexp.mmlogistix@bp0.work',
            'fintreasury.mmlogistix@bp0.work', 'finfa.mmlogistix@bp0.work');
        """
    )

    op.execute(
        """
        INSERT INTO notification_templates
            (event_key, display_name, description, default_email, default_in_app,
             user_overridable, sort_order)
        VALUES
            ('finance.daily_log', 'Finance daily activity digest',
             'Daily CSV digest of finance_activity_log to CFO.', true, false, false, 200),
            ('manager.escalation.request', 'Manager escalation request',
             'Executive case escalated to manager for Approve/Reject/Escalate.', true, false, false, 210),
            ('manager.outbound.approval.request', 'Outbound email approval request',
             'Client-facing email awaiting manager approval before send.', true, false, false, 220)
        ON CONFLICT (event_key) DO NOTHING;
        """
    )

    op.execute(
        """
        INSERT INTO system_settings (key, value, value_type, description, category)
        VALUES
            ('last_finance_log_sent_at', '', 'string',
             'ISO timestamp of last finance daily digest send', 'mail'),
            ('daily_log.timezone', 'Asia/Singapore', 'string',
             'Business date timezone for finance daily log', 'mail')
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM system_settings WHERE key IN ('last_finance_log_sent_at', 'daily_log.timezone');
        DELETE FROM notification_templates WHERE event_key IN (
            'finance.daily_log', 'manager.escalation.request', 'manager.outbound.approval.request'
        );
        """
    )
    op.drop_index("finance_activity_log_case_idx", table_name="finance_activity_log")
    op.drop_index("finance_activity_log_mailbox_idx", table_name="finance_activity_log")
    op.drop_index("finance_activity_log_business_date_idx", table_name="finance_activity_log")
    op.drop_index("finance_activity_log_occurred_idx", table_name="finance_activity_log")
    op.drop_table("finance_activity_log")
