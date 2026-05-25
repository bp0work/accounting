"""client_admin_tables — tenant_profiles, agreements, accounting_periods, regulatory_documents."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260531_049"
down_revision = "20260530_048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_profiles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trading_name", sa.String(255), nullable=True),
        sa.Column("uen", sa.String(100), nullable=True),
        sa.Column("gst_registration_number", sa.String(100), nullable=True),
        sa.Column("registered_address", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.execute(
        """
        CREATE TYPE accounting_period_status AS ENUM ('open', 'review', 'closed');
        """
    )
    op.create_table(
        "accounting_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("gl_cutoff_date", sa.Date(), nullable=False),
        sa.Column("trial_balance_reviewer", sa.String(255), nullable=False, server_default="finfa.mmlogistix@bp0.work"),
        sa.Column("trial_balance_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_balance_approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("gl_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gl_closed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", postgresql.ENUM("open", "review", "closed", name="accounting_period_status", create_type=False), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "period_year", "period_month", name="accounting_periods_tenant_period_uq"),
    )
    op.create_table(
        "rental_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_address", sa.Text(), nullable=False),
        sa.Column("monthly_rent_sgd", sa.Numeric(19, 4), nullable=False),
        sa.Column("business_use_percent", sa.Numeric(5, 2), nullable=False, server_default="100"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("landlord_name", sa.String(255), nullable=True),
        sa.Column("landlord_contact", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_table(
        "director_expense_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("director_name", sa.String(255), nullable=False),
        sa.Column("director_email", sa.String(255), nullable=False),
        sa.Column("authorised_expense_types", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("monthly_limit_sgd", sa.Numeric(19, 4), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_table(
        "regulatory_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("wasabi_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False, server_default="application/pdf"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("regulatory_documents_tenant_idx", "regulatory_documents", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("regulatory_documents_tenant_idx", table_name="regulatory_documents")
    op.drop_table("regulatory_documents")
    op.drop_table("director_expense_agreements")
    op.drop_table("rental_agreements")
    op.drop_table("accounting_periods")
    op.drop_table("tenant_profiles")
    op.execute("DROP TYPE IF EXISTS accounting_period_status;")
