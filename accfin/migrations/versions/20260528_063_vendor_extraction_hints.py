"""vendor_extraction_hints — `0.14.23-vendor-extraction-hints`."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260528_063"
down_revision = "20260527_062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_extraction_hints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_label", sa.String(255), nullable=False),
        sa.Column("field_location", sa.String(100), nullable=True),
        sa.Column("example_value", sa.String(255), nullable=True),
        sa.Column("date_format", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
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
        sa.UniqueConstraint("tenant_id", "vendor_name", "field_name", name="uq_vendor_hint_field"),
    )
    op.create_index(
        "ix_vendor_extraction_hints_tenant_vendor",
        "vendor_extraction_hints",
        ["tenant_id", "vendor_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_extraction_hints_tenant_vendor", table_name="vendor_extraction_hints")
    op.drop_table("vendor_extraction_hints")
