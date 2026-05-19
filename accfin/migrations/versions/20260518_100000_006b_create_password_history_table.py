"""create_password_history_table

Revision ID: 20260510_006b
Revises: 20260510_006

Schema source: 06_Database_Schema_Design.md §3.6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_006b"
down_revision = "20260510_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("password_history_user_id_idx", "password_history", ["user_id"])
    op.execute("""
        CREATE INDEX password_history_user_created_idx
        ON password_history(user_id, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS password_history_user_created_idx;")
    op.drop_index("password_history_user_id_idx", table_name="password_history")
    op.drop_table("password_history")
