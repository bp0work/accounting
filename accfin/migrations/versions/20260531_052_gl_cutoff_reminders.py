"""gl_cutoff_reminders — email recipients for GL cutoff notifications."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260531_052"
down_revision = "20260531_051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gl_cutoff_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("notify_7_days", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_3_days", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_1_day", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_on_date", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("gl_cutoff_reminders_tenant_idx", "gl_cutoff_reminders", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("gl_cutoff_reminders_tenant_idx", table_name="gl_cutoff_reminders")
    op.drop_table("gl_cutoff_reminders")
