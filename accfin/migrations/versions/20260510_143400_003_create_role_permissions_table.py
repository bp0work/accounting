"""create_role_permissions_table

Revision ID: 20260510_003
Revises: 20260510_002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_003"
down_revision = "20260510_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "role_permissions_permission_id_idx",
        "role_permissions",
        ["permission_id"],
    )


def downgrade() -> None:
    op.drop_index("role_permissions_permission_id_idx", table_name="role_permissions")
    op.drop_table("role_permissions")
