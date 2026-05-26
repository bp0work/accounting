"""Seed default payment terms — Phase 13 (`0.14.8`)."""

from alembic import op

revision = "20260531_056"
down_revision = "20260531_055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO payment_terms (code, label, due_days)
        VALUES
            ('COD', 'Cash on delivery', 0),
            ('NET7', 'Net 7 days', 7),
            ('NET30', 'Net 30 days', 30),
            ('NET60', 'Net 60 days', 60)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM payment_terms
        WHERE code IN ('COD', 'NET7', 'NET30', 'NET60');
        """
    )
