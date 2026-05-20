"""create_user_notification_preferences_table — `06` §3.8."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260526_035"
down_revision = "20260526_034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notification_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "quiet_hours",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "channels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text('\'{"email": true, "in_app": true}\'::jsonb'),
        ),
        sa.Column(
            "subscriptions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="user_notification_preferences_user_id_key"),
        sa.CheckConstraint(
            "jsonb_typeof(subscriptions) = 'array'",
            name="user_notification_preferences_subscriptions_is_array",
        ),
    )
    op.create_index(
        "user_notification_preferences_user_id_idx",
        "user_notification_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("user_notification_preferences")
