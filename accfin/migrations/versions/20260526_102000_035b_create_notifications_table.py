"""create_notifications_table — `06` §3.9 / `18` §3."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260526_035b"
down_revision = "20260526_035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_number", sa.String(20), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("source_event_id", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
    )
    op.create_index("notifications_user_id_idx", "notifications", ["user_id"])
    op.execute(
        """
        CREATE INDEX notifications_user_unread_idx ON notifications(user_id, is_read)
            WHERE is_read = FALSE;
        """
    )
    op.create_index("notifications_created_at_idx", "notifications", ["created_at"])
    op.create_index("notifications_source_event_id_idx", "notifications", ["source_event_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX notifications_user_event_dedup_idx
            ON notifications(user_id, source_event_id);
        """
    )


def downgrade() -> None:
    op.drop_table("notifications")
