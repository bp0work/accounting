"""create_cases_table — `06` §4.2, `16` §11.4 circular FK with emails."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260521_012"
down_revision = "20260521_011"
branch_labels = None
depends_on = None

case_type = postgresql.ENUM(name="case_type", create_type=False)
case_status = postgresql.ENUM(
    "inbound",
    "classified",
    "processing",
    "pending_approval",
    "approved",
    "posted",
    "completed",
    "rejected",
    "exception",
    "manual_review",
    "on_hold",
    name="case_status",
    create_type=False,
)
case_priority = postgresql.ENUM(
    "critical", "high", "medium", "low", name="case_priority", create_type=False
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE case_status AS ENUM (
            'inbound', 'classified', 'processing', 'pending_approval',
            'approved', 'posted', 'completed', 'rejected', 'exception',
            'manual_review', 'on_hold'
        );
        """
    )
    op.execute("CREATE TYPE case_priority AS ENUM ('critical', 'high', 'medium', 'low');")

    op.create_table(
        "cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("case_number", sa.String(20), nullable=False),
        sa.Column("type", case_type, nullable=False),
        sa.Column(
            "status",
            case_status,
            nullable=False,
            server_default=sa.text("'inbound'::case_status"),
        ),
        sa.Column(
            "priority",
            case_priority,
            nullable=False,
            server_default=sa.text("'medium'::case_priority"),
        ),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("stp_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("counterparty_name", sa.String(255), nullable=True),
        sa.Column("amount_value", sa.Numeric(19, 4), nullable=True),
        sa.Column("amount_currency", sa.CHAR(3), server_default="SGD"),
        sa.Column("converted_amount_value", sa.Numeric(19, 4), nullable=True),
        sa.Column("converted_amount_currency", sa.CHAR(3), server_default="SGD"),
        sa.Column("exchange_rate", sa.Numeric(19, 8), server_default="1.0"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_approval_tier", sa.Integer(), nullable=True),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "risk_flags",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("classification_metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("workflow_metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_status", sa.String(20), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=False, server_default="system"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparty.id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("case_number", name="cases_case_number_key"),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="cases_confidence_score_check",
        ),
        sa.CheckConstraint(
            "current_approval_tier BETWEEN 1 AND 3",
            name="cases_approval_tier_check",
        ),
        sa.CheckConstraint(
            "sla_status IS NULL OR sla_status IN ('on_track', 'at_risk', 'breached')",
            name="cases_sla_status_check",
        ),
    )
    op.create_foreign_key(
        "cases_parent_case_id_fkey", "cases", "cases", ["parent_case_id"], ["id"]
    )
    op.create_index("cases_case_number_idx", "cases", ["case_number"])
    op.create_index("cases_type_idx", "cases", ["type"])
    op.create_index("cases_status_idx", "cases", ["status"])
    op.create_index("cases_priority_idx", "cases", ["priority"])
    op.create_index("cases_email_id_idx", "cases", ["email_id"])
    op.create_index("cases_counterparty_id_idx", "cases", ["counterparty_id"])
    op.create_index("cases_created_at_idx", "cases", ["created_at"])
    op.create_index("cases_status_priority_idx", "cases", ["status", "priority"])
    op.create_index("cases_type_status_idx", "cases", ["type", "status"])
    op.execute(
        """
        CREATE TRIGGER cases_updated_at
            BEFORE UPDATE ON cases
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )
    op.create_foreign_key("cases_email_id_fkey", "cases", "emails", ["email_id"], ["id"])
    op.create_foreign_key("emails_case_id_fkey", "emails", "cases", ["case_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("emails_case_id_fkey", "emails", type_="foreignkey")
    op.drop_constraint("cases_email_id_fkey", "cases", type_="foreignkey")
    op.drop_table("cases")
    op.execute("DROP TYPE IF EXISTS case_priority;")
    op.execute("DROP TYPE IF EXISTS case_status;")
