"""create_system_settings_table — `06` §13.2."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_038"
down_revision = "20260527_037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
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
            "value_type IN ('string', 'integer', 'float', 'boolean', 'json')",
            name="system_settings_value_type_check",
        ),
    )
    op.create_index("system_settings_key_idx", "system_settings", ["key"])
    op.create_index("system_settings_category_idx", "system_settings", ["category"])

    op.execute(
        """
        INSERT INTO system_settings (key, value, value_type, description, category)
        VALUES
            ('audit.retention_days', '2555', 'integer',
             'Audit log retention in days (7 years)', 'audit'),
            ('monitoring.prometheus_enabled', 'true', 'boolean',
             'Expose Prometheus metrics on FastAPI', 'monitoring'),
            ('monitoring.integrity_check_batch_size', '5000', 'integer',
             'Max rows per integrity-check API call', 'monitoring'),
            ('platform.version_label', '0.10.0-phase10', 'string',
             'Displayed platform version label', 'general')
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("system_settings_category_idx", table_name="system_settings")
    op.drop_index("system_settings_key_idx", table_name="system_settings")
    op.drop_table("system_settings")
