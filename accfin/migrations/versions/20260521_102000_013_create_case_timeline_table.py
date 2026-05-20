"""create_case_timeline_table — `06` §4.3."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260521_013"
down_revision = "20260521_012"
branch_labels = None
depends_on = None

case_status = postgresql.ENUM(name="case_status", create_type=False)


def upgrade() -> None:
    op.create_table(
        "case_timeline",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_status", case_status, nullable=True),
        sa.Column("to_status", case_status, nullable=True),
        sa.Column("actor", sa.String(50), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index("case_timeline_case_id_idx", "case_timeline", ["case_id"])
    op.create_index("case_timeline_created_at_idx", "case_timeline", ["created_at"])


def downgrade() -> None:
    op.drop_table("case_timeline")
