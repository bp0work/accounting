"""seed_expense_policies — `19` §13."""

from alembic import op

revision = "20260528_044"
down_revision = "20260528_043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_admin_id UUID;
        BEGIN
            SELECT id INTO v_admin_id FROM users WHERE username = 'system.mmlogistix' LIMIT 1;
            IF v_admin_id IS NULL THEN
                SELECT id INTO v_admin_id FROM users LIMIT 1;
            END IF;

            INSERT INTO expense_policies
                (name, display_name, description, applies_to_all_categories,
                 applies_to_all_departments, requires_receipt_above, requires_approval_above,
                 version, created_by)
            VALUES
                ('global_receipt_policy', 'Global Receipt Requirement',
                 'All expense line items above SGD 50 require a receipt.',
                 TRUE, TRUE, 50.00, 500.00, '1.0.0', v_admin_id),
                ('global_approval_threshold', 'Global Approval Threshold',
                 'Claims exceeding SGD 500 require Finance Officer approval.',
                 TRUE, TRUE, 50.00, 500.00, '1.0.0', v_admin_id)
            ON CONFLICT (name) DO NOTHING;

            INSERT INTO expense_policies
                (name, display_name, description, category, applies_to_all_categories,
                 applies_to_all_departments, daily_limit, per_claim_limit,
                 requires_receipt_above, requires_approval_above, version, created_by)
            VALUES
                ('meals_daily_limit', 'Meals Daily Limit',
                 'Meal expenses capped at SGD 80 per day per claim.',
                 'meals', FALSE, TRUE, 80.00, NULL, 30.00, 500.00, '1.0.0', v_admin_id),
                ('accommodation_limit', 'Accommodation Limit',
                 'Accommodation capped at SGD 250 per night.',
                 'accommodation', FALSE, TRUE, 250.00, NULL, 50.00, 500.00, '1.0.0', v_admin_id),
                ('entertainment_approval', 'Entertainment Approval Required',
                 'All entertainment expenses require Finance Manager approval.',
                 'entertainment', FALSE, TRUE, NULL, NULL, 1.00, 1.00, '1.0.0', v_admin_id),
                ('airfare_approval', 'Airfare Approval Required',
                 'All airfare expenses above SGD 200 require Finance Officer approval.',
                 'airfare', FALSE, TRUE, NULL, NULL, 50.00, 200.00, '1.0.0', v_admin_id)
            ON CONFLICT (name) DO NOTHING;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM expense_policies WHERE name IN (
            'global_receipt_policy', 'global_approval_threshold', 'meals_daily_limit',
            'accommodation_limit', 'entertainment_approval', 'airfare_approval'
        );
        """
    )
