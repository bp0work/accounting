"""create_queue_messages_table — `06` §8.1."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260522_026"
down_revision = "20260522_025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE queue_message_status AS ENUM (
            'pending', 'processing', 'failed', 'dead'
        );
        """
    )
    status = postgresql.ENUM(name="queue_message_status", create_type=False)

    op.create_table(
        "queue_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("queue_name", sa.String(100), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("status", status, nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("worker_name", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
    )
    op.create_index("queue_messages_queue_status_idx", "queue_messages", ["queue_name", "status"])
    op.create_index("queue_messages_case_id_idx", "queue_messages", ["case_id"])
    op.create_index("queue_messages_created_at_idx", "queue_messages", ["created_at"])
    op.execute(
        """
        CREATE INDEX queue_messages_scheduled_idx ON queue_messages(scheduled_at, status)
            WHERE status = 'pending';
        """
    )
    op.execute(
        """
        CREATE TRIGGER queue_messages_updated_at
            BEFORE UPDATE ON queue_messages
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.drop_table("queue_messages")
    op.execute("DROP TYPE IF EXISTS queue_message_status;")
