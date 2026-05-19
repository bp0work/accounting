"""create_users_table

Revision ID: 20260510_004
Revises: 20260510_003

Schema source: 06_Database_Schema_Design.md §3.1
tenant_id added in 006d_create_tenants_table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_004"
down_revision = "20260510_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id"),
            nullable=False,
        ),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "two_factor_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("two_factor_secret", sa.String(255), nullable=True),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("username", name="users_username_key"),
        sa.UniqueConstraint("email", name="users_email_key"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'locked')",
            name="users_status_check",
        ),
    )
    op.create_index("users_username_idx", "users", ["username"])
    op.create_index("users_role_id_idx", "users", ["role_id"])
    op.create_index("users_email_idx", "users", ["email"])
    op.execute("""
        CREATE INDEX users_status_idx ON users(status)
        WHERE status = 'active';
    """)
    op.execute("""
        CREATE TRIGGER users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS users_updated_at ON users;")
    op.execute("DROP INDEX IF EXISTS users_status_idx;")
    op.drop_index("users_email_idx", table_name="users")
    op.drop_index("users_role_id_idx", table_name="users")
    op.drop_index("users_username_idx", table_name="users")
    op.drop_table("users")
