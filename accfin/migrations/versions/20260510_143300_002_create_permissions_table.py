"""create_permissions_table

Revision ID: 20260510_002
Revises: 20260510_001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_002"
down_revision = "20260510_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="permissions_code_key"),
    )
    op.create_index("permissions_category_idx", "permissions", ["category"])


def downgrade() -> None:
    op.drop_index("permissions_category_idx", table_name="permissions")
    op.drop_table("permissions")
