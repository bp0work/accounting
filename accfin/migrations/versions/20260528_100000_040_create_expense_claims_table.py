"""create_expense_claims_table — `19` §3.1."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260528_040"
down_revision = "20260527_039b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE expense_claim_status AS ENUM (
            'draft', 'submitted', 'processing', 'pending_approval',
            'approved', 'rejected', 'posted', 'completed', 'exception', 'manual_review'
        );
        """
    )
    op.create_table(
        "expense_claims",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("case_number", sa.String(20), nullable=False),
        sa.Column(
            "claimant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("claimant_name", sa.String(200), nullable=False),
        sa.Column(
            "submission_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("claim_period_from", sa.Date(), nullable=False),
        sa.Column("claim_period_to", sa.Date(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("project_code", sa.String(50), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="SGD"),
        sa.Column(
            "total_claimed",
            sa.Numeric(19, 4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("total_approved", sa.Numeric(19, 4), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="expense_claim_status", create_type=False),
            nullable=False,
            server_default=sa.text("'submitted'::expense_claim_status"),
        ),
        sa.Column(
            "policy_violations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "risk_flags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("approval_tier", sa.SmallInteger(), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=True,
        ),
        sa.Column(
            "workflow_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("extraction_confidence", sa.Numeric(4, 2), nullable=True),
        sa.Column("stp_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("submitted_via", sa.String(20), nullable=False, server_default="email"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "approval_tier IS NULL OR approval_tier BETWEEN 1 AND 3",
            name="expense_claims_approval_tier_check",
        ),
        sa.CheckConstraint(
            "submitted_via IN ('email','ui','api')",
            name="expense_claims_submitted_via_check",
        ),
        sa.CheckConstraint("total_claimed >= 0", name="expense_claims_total_claimed_check"),
    )
    op.create_index("expense_claims_case_id_idx", "expense_claims", ["case_id"])
    op.create_index("expense_claims_claimant_id_idx", "expense_claims", ["claimant_id"])
    op.create_index("expense_claims_status_idx", "expense_claims", ["status"])
    op.create_index("expense_claims_submission_date_idx", "expense_claims", ["submission_date"])
    op.create_index(
        "expense_claims_period_idx", "expense_claims", ["claim_period_from", "claim_period_to"]
    )
    op.execute(
        """
        CREATE TRIGGER expense_claims_updated_at
        BEFORE UPDATE ON expense_claims
        FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS expense_claims_updated_at ON expense_claims;")
    op.drop_index("expense_claims_period_idx", table_name="expense_claims")
    op.drop_index("expense_claims_submission_date_idx", table_name="expense_claims")
    op.drop_index("expense_claims_status_idx", table_name="expense_claims")
    op.drop_index("expense_claims_claimant_id_idx", table_name="expense_claims")
    op.drop_index("expense_claims_case_id_idx", table_name="expense_claims")
    op.drop_table("expense_claims")
    op.execute("DROP TYPE IF EXISTS expense_claim_status;")
