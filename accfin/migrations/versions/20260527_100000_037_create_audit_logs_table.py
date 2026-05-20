"""create_audit_logs_table — `06` §13.1."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_037"
down_revision = "20260526_036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE audit_action AS ENUM (
            'create', 'update', 'delete', 'approve', 'reject', 'post',
            'login', 'logout', 'export', 'override', 'escalate', 'delegate',
            'merge', 'split', 'match', 'unmatch', 'retry', 'cancel'
        );
        """
    )
    op.execute(
        """
        CREATE TYPE audit_entity_type AS ENUM (
            'case', 'approval', 'journal_entry', 'policy', 'user', 'role',
            'workflow', 'email', 'queue_message', 'reconciliation', 'setting'
        );
        """
    )

    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("action", postgresql.ENUM(name="audit_action", create_type=False), nullable=False),
        sa.Column(
            "entity_type",
            postgresql.ENUM(name="audit_entity_type", create_type=False),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=True,
        ),
        sa.Column("case_number", sa.String(20), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_name", sa.String(100), nullable=True),
        sa.Column("user_ip_address", postgresql.INET(), nullable=True),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("tamper_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index("audit_logs_timestamp_idx", "audit_logs", ["timestamp"])
    op.create_index("audit_logs_entity_idx", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("audit_logs_case_id_idx", "audit_logs", ["case_id"])
    op.create_index("audit_logs_user_id_idx", "audit_logs", ["user_id"])
    op.create_index("audit_logs_action_idx", "audit_logs", ["action"])
    op.create_index("audit_logs_correlation_idx", "audit_logs", ["correlation_id"])
    op.create_index(
        "audit_logs_timestamp_entity_idx", "audit_logs", ["timestamp", "entity_type"]
    )


def downgrade() -> None:
    op.drop_index("audit_logs_timestamp_entity_idx", table_name="audit_logs")
    op.drop_index("audit_logs_correlation_idx", table_name="audit_logs")
    op.drop_index("audit_logs_action_idx", table_name="audit_logs")
    op.drop_index("audit_logs_user_id_idx", table_name="audit_logs")
    op.drop_index("audit_logs_case_id_idx", table_name="audit_logs")
    op.drop_index("audit_logs_entity_idx", table_name="audit_logs")
    op.drop_index("audit_logs_timestamp_idx", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_entity_type;")
    op.execute("DROP TYPE IF EXISTS audit_action;")
