"""vendor_extraction_hints case-insensitive uniqueness.

Fixes duplicate vendor hints created with different casing (e.g. "ACRA" vs "Acra")
by deduping and enforcing a unique index on (tenant_id, lower(vendor_name), field_name).
"""

from alembic import op

revision = "20260603_071"
down_revision = "20260603_070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the most recently updated row per (tenant_id, lower(vendor_name), field_name).
    op.execute(
        """
        WITH ranked AS (
          SELECT
            id,
            ROW_NUMBER() OVER (
              PARTITION BY tenant_id, LOWER(vendor_name), field_name
              ORDER BY updated_at DESC, created_at DESC
            ) AS rn
          FROM vendor_extraction_hints
        )
        DELETE FROM vendor_extraction_hints v
        USING ranked r
        WHERE v.id = r.id
          AND r.rn > 1;
        """
    )

    # Enforce case-insensitive uniqueness for future upserts.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_hint_field_ci
        ON vendor_extraction_hints (tenant_id, LOWER(vendor_name), field_name);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_vendor_hint_field_ci;")

