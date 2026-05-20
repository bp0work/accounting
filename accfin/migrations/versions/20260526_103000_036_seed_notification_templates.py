"""seed_notification_templates — `06` §19.6."""

from alembic import op

revision = "20260526_036"
down_revision = "20260526_035b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO notification_templates
            (event_key, display_name, description, default_email, default_in_app,
             user_overridable, sort_order)
        VALUES
            ('approval.requested', 'Approval requested',
             'A new item requires your approval.', true, true, true, 10),
            ('approval.sla_at_risk', 'Approval SLA at risk',
             'An approval is approaching its SLA deadline.', true, true, true, 20),
            ('approval.escalated', 'Approval escalated',
             'An approval was escalated to a higher tier.', true, true, true, 30),
            ('approval.approved', 'Approval completed',
             'An approval you follow was approved.', false, true, true, 40),
            ('approval.rejected', 'Approval rejected',
             'An approval you follow was rejected.', false, true, true, 50),
            ('case.assigned', 'Case assigned',
             'A case was assigned to you.', false, true, true, 60),
            ('case.status_changed', 'Case status changed',
             'A case you follow changed status.', false, true, true, 70),
            ('expense.claim.submitted', 'Expense claim submitted',
             'A new expense claim requires your approval.', true, true, true, 80),
            ('expense.claim.approved', 'Expense claim approved',
             'Your expense claim was approved.', true, true, true, 90),
            ('expense.claim.rejected', 'Expense claim rejected',
             'Your expense claim was rejected.', true, true, true, 100)
        ON CONFLICT (event_key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM notification_templates WHERE event_key IN (
            'approval.requested', 'approval.sla_at_risk', 'approval.escalated',
            'approval.approved', 'approval.rejected', 'case.assigned', 'case.status_changed',
            'expense.claim.submitted', 'expense.claim.approved', 'expense.claim.rejected'
        );
        """
    )
