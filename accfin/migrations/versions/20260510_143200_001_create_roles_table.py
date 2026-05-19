"""create_roles_table

Revision ID: 20260510_001
Revises:
Create Date: 2026-05-10 14:32:00

Schema source: 06_Database_Schema_Design.md §3.2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION auto_update_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.UniqueConstraint("name", name="roles_name_key"),
    )
    op.create_index("roles_name_idx", "roles", ["name"])
    op.execute("""
        CREATE TRIGGER roles_updated_at
            BEFORE UPDATE ON roles
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS roles_updated_at ON roles;")
    op.drop_index("roles_name_idx", table_name="roles")
    op.drop_table("roles")
    op.execute("DROP FUNCTION IF EXISTS auto_update_timestamp();")
