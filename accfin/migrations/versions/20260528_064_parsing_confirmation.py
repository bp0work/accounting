"""parsing_confirmation — `0.14.25-parsing-confirmation`."""

import sqlalchemy as sa
from alembic import op

revision = "20260528_064"
down_revision = "20260528_063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("ALTER TYPE case_status ADD VALUE IF NOT EXISTS 'pending_confirmation'")
    )
    op.add_column(
        "mail_gateway_config",
        sa.Column(
            "require_parsing_confirmation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mail_gateway_config", "require_parsing_confirmation")
    # PostgreSQL does not support removing enum values; pending_confirmation remains.
