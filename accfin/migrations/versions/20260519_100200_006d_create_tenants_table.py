"""create_tenants_table

Revision ID: 20260510_006d
Revises: 20260510_006c

Creates tenants, adds users.tenant_id, seeds MVP tenant — 06 §13.2a, §19.9
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_006d"
down_revision = "20260510_006c"
branch_labels = None
depends_on = None

TENANT_MMLOGISTIX = "00000000-0000-0000-0000-000000000200"
USER_CLIENT_ADMIN = "00000000-0000-0000-0000-000000000101"


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("slug", name="tenants_slug_key"),
    )
    op.create_index("tenants_slug_idx", "tenants", ["slug"])
    op.execute("""
        CREATE INDEX tenants_active_idx ON tenants(is_active) WHERE is_active = TRUE;
    """)
    op.execute("""
        CREATE TRIGGER tenants_updated_at
            BEFORE UPDATE ON tenants
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
    """)

    op.add_column(
        "users",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=True,
        ),
    )
    op.create_index("users_tenant_id_idx", "users", ["tenant_id"])

    op.execute(
        sa.text(f"""
        INSERT INTO tenants (id, slug, display_name, is_active) VALUES
        ('{TENANT_MMLOGISTIX}', 'mmlogistix', 'MM Logistix Pte Ltd', true)
        ON CONFLICT (id) DO NOTHING;
    """)
    )

    op.execute(
        sa.text(f"""
        UPDATE users SET tenant_id = '{TENANT_MMLOGISTIX}'
        WHERE id = '{USER_CLIENT_ADMIN}';
    """)
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
        UPDATE users SET tenant_id = NULL WHERE tenant_id = '{TENANT_MMLOGISTIX}';
    """)
    )
    op.drop_index("users_tenant_id_idx", table_name="users")
    op.drop_column("users", "tenant_id")
    op.execute("DROP TRIGGER IF EXISTS tenants_updated_at ON tenants;")
    op.execute("DROP INDEX IF EXISTS tenants_active_idx;")
    op.drop_index("tenants_slug_idx", table_name="tenants")
    op.drop_table("tenants")
