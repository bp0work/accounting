"""add ar_soa_request to case_type enum — `06` §18.4, `17` §4.7."""

from alembic import op

revision = "20260523_026c"
down_revision = "20260522_026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE case_type ADD VALUE IF NOT EXISTS 'ar_soa_request';")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing enum values safely
