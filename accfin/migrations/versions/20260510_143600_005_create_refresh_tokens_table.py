"""create_refresh_tokens_table

Revision ID: 20260510_005
Revises: 20260510_004
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_005"
down_revision = "20260510_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
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
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("refresh_tokens_user_id_idx", "refresh_tokens", ["user_id"])
    op.create_index("refresh_tokens_token_hash_idx", "refresh_tokens", ["token_hash"])
    op.execute("""
        CREATE INDEX refresh_tokens_expires_at_idx ON refresh_tokens(expires_at)
        WHERE revoked_at IS NULL;
    """)
    op.execute("""
        CREATE TRIGGER refresh_tokens_updated_at
            BEFORE UPDATE ON refresh_tokens
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS refresh_tokens_updated_at ON refresh_tokens;")
    op.execute("DROP INDEX IF EXISTS refresh_tokens_expires_at_idx;")
    op.drop_index("refresh_tokens_token_hash_idx", table_name="refresh_tokens")
    op.drop_index("refresh_tokens_user_id_idx", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
