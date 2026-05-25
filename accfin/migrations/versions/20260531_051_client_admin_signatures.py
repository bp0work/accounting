"""client_admin_signatures — email signature fields, regulatory document_key."""

from alembic import op
import sqlalchemy as sa

revision = "20260531_051"
down_revision = "20260531_050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_profiles", sa.Column("email_signature_html", sa.Text(), nullable=True))
    op.add_column("tenant_profiles", sa.Column("email_signature_plain", sa.Text(), nullable=True))
    op.add_column("regulatory_documents", sa.Column("document_key", sa.String(64), nullable=True))
    op.create_index(
        "regulatory_documents_tenant_key_uq",
        "regulatory_documents",
        ["tenant_id", "document_key"],
        unique=True,
        postgresql_where=sa.text("document_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("regulatory_documents_tenant_key_uq", table_name="regulatory_documents")
    op.drop_column("regulatory_documents", "document_key")
    op.drop_column("tenant_profiles", "email_signature_plain")
    op.drop_column("tenant_profiles", "email_signature_html")
