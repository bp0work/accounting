"""create_workflow_tables — `06` §4.6–4.8."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260521_016"
down_revision = "20260521_015"
branch_labels = None
depends_on = None

case_status = postgresql.ENUM(name="case_status", create_type=False)


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("case_type", postgresql.ENUM(name="case_type", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("definition", postgresql.JSONB(), nullable=False, server_default="{}"),
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
        sa.UniqueConstraint("name", "version", name="workflow_definitions_name_version_key"),
    )
    op.execute(
        """
        CREATE TRIGGER workflow_definitions_updated_at
            BEFORE UPDATE ON workflow_definitions
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )

    op.create_table(
        "workflow_instances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_state", case_status, nullable=False),
        sa.Column("context", postgresql.JSONB(), server_default="{}"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["definition_id"], ["workflow_definitions.id"]),
        sa.UniqueConstraint("case_id", name="workflow_instances_case_id_key"),
    )
    op.create_index("workflow_instances_case_id_idx", "workflow_instances", ["case_id"])
    op.execute(
        """
        CREATE TRIGGER workflow_instances_updated_at
            BEFORE UPDATE ON workflow_instances
            FOR EACH ROW EXECUTE FUNCTION auto_update_timestamp();
        """
    )

    op.create_table(
        "workflow_transitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", case_status, nullable=False),
        sa.Column("to_state", case_status, nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(50), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["instance_id"], ["workflow_instances.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "workflow_transitions_instance_id_idx", "workflow_transitions", ["instance_id"]
    )


def downgrade() -> None:
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_definitions")
