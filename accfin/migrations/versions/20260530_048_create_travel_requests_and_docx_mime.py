"""create_travel_requests_table — `19` travel pre-approval matching."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260530_048"
down_revision = "20260530_047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE travel_request_status AS ENUM (
            'draft', 'submitted', 'approved', 'rejected', 'cancelled'
        );
        """
    )
    op.create_table(
        "travel_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("request_number", sa.String(30), nullable=False, unique=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("employee_email", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=True),
        sa.Column("travel_from", sa.Date(), nullable=False),
        sa.Column("travel_to", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="travel_request_status", create_type=False),
            nullable=False,
            server_default=sa.text("'approved'::travel_request_status"),
        ),
        sa.Column("purpose", sa.Text(), nullable=True),
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
    )
    op.create_index("travel_requests_employee_id_idx", "travel_requests", ["employee_id"])
    op.create_index(
        "travel_requests_employee_dates_idx",
        "travel_requests",
        ["employee_id", "travel_from", "travel_to"],
    )

    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    op.execute(
        f"""
        UPDATE mail_gateway_config
        SET allowed_attachment_types = (
            SELECT ARRAY(
                SELECT DISTINCT unnest(
                    allowed_attachment_types || ARRAY['{docx}']::text[]
                )
            )
        )
        WHERE mailbox_mode = 'executive_agent';
        """
    )


def downgrade() -> None:
    op.drop_index("travel_requests_employee_dates_idx", table_name="travel_requests")
    op.drop_index("travel_requests_employee_id_idx", table_name="travel_requests")
    op.drop_table("travel_requests")
    op.execute("DROP TYPE IF EXISTS travel_request_status;")

    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    op.execute(
        f"""
        UPDATE mail_gateway_config
        SET allowed_attachment_types = array_remove(
            allowed_attachment_types, '{docx}'
        )
        WHERE mailbox_mode = 'executive_agent';
        """
    )
