"""tenant_tax_codes — Phase 13 (`0.14.8`)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260531_057"
down_revision = "20260531_056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_tax_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("output_gl_account_code", sa.String(20), nullable=True),
        sa.Column("input_gl_account_code", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("rate >= 0 AND rate <= 1", name="tenant_tax_codes_rate_range"),
        sa.CheckConstraint(
            "direction IN ('output', 'input', 'both')",
            name="tenant_tax_codes_direction_chk",
        ),
    )


def downgrade() -> None:
    op.drop_table("tenant_tax_codes")
