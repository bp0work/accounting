"""add_audit_log_partitioning — `06` §13.1 partitioning recommendation."""

from alembic import op

revision = "20260527_039"
down_revision = "20260527_038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # BRIN index for time-range scans; monthly declarative partitions can be added in production.
    op.execute(
        """
        CREATE INDEX audit_logs_timestamp_brin_idx
            ON audit_logs USING BRIN (timestamp);
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_audit_log_month_partition(p_month date)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            part_name text;
            start_ts timestamptz;
            end_ts timestamptz;
        BEGIN
            start_ts := date_trunc('month', p_month);
            end_ts := start_ts + interval '1 month';
            part_name := 'audit_logs_' || to_char(start_ts, 'YYYY_MM');
            IF to_regclass(part_name) IS NOT NULL THEN
                RETURN;
            END IF;
            -- No-op for non-partitioned table; documents ops hook for pg_partman migration.
            PERFORM 1;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ensure_audit_log_month_partition(date);")
    op.execute("DROP INDEX IF EXISTS audit_logs_timestamp_brin_idx;")
