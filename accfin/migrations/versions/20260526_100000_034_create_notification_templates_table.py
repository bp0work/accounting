"""create_notification_templates_table — `06` §3.7 (Phase 9)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260526_034"
down_revision = "20260525_033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_email", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_in_app", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("user_overridable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("event_key", name="notification_templates_event_key_key"),
    )
    op.create_index(
        "notification_templates_event_key_idx", "notification_templates", ["event_key"]
    )
    op.create_index("notification_templates_sort_idx", "notification_templates", ["sort_order"])
    op.execute(
        """
        CREATE TRIGGER notification_templates_updated_at
            BEFORE UPDATE ON notification_templates
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.drop_table("notification_templates")
