"""create_policies_and_approvals — `06` §4.9–4.10."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260521_017"
down_revision = "20260521_016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE approval_status AS ENUM (
            'pending', 'approved', 'rejected', 'escalated', 'expired'
        );
        """
    )
    approval_status = postgresql.ENUM(name="approval_status", create_type=False)

    op.create_table(
        "policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("policy_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("name", "version", name="policies_name_version_key"),
        sa.CheckConstraint(
            "policy_type IN ('approval', 'classification', 'routing', 'validation', 'stp')",
            name="policies_policy_type_check",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER policies_updated_at
            BEFORE UPDATE ON policies
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )

    op.create_table(
        "approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("status", approval_status, nullable=False, server_default="pending"),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_value", sa.Numeric(19, 4), nullable=True),
        sa.Column("amount_currency", sa.CHAR(3), server_default="SGD"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.CheckConstraint("tier BETWEEN 1 AND 3", name="approvals_tier_check"),
    )
    op.create_index("approvals_case_id_idx", "approvals", ["case_id"])
    op.create_index("approvals_status_idx", "approvals", ["status"])
    op.execute(
        """
        CREATE TRIGGER approvals_updated_at
            BEFORE UPDATE ON approvals
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("policies")
    op.execute("DROP TYPE IF EXISTS approval_status;")
