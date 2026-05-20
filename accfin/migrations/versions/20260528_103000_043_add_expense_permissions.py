"""add_expense_permissions — `19` §3.4."""

from alembic import op
import sqlalchemy as sa

revision = "20260528_043"
down_revision = "20260528_042"
branch_labels = None
depends_on = None

ROLE_CFO = "00000000-0000-0000-0000-000000000002"
ROLE_FINANCE_MANAGER = "00000000-0000-0000-0000-000000000003"
ROLE_FINANCE_OFFICER = "00000000-0000-0000-0000-000000000004"
ROLE_ACCOUNTS_CLERK = "00000000-0000-0000-0000-000000000005"
ROLE_AUDITOR = "00000000-0000-0000-0000-000000000006"
ROLE_FINANCIAL_ANALYST = "00000000-0000-0000-0000-000000000009"


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, category, action, description) VALUES
            ('expenses:read', 'expenses', 'read', 'View expense claims and line items'),
            ('expenses:write', 'expenses', 'write', 'Create and update expense claims'),
            ('expenses:approve', 'expenses', 'approve', 'Approve expense claims')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    grants = [
        (ROLE_CFO, ("expenses:read", "expenses:write", "expenses:approve")),
        (ROLE_FINANCE_MANAGER, ("expenses:read", "expenses:write", "expenses:approve")),
        (ROLE_FINANCE_OFFICER, ("expenses:read", "expenses:write", "expenses:approve")),
        (ROLE_ACCOUNTS_CLERK, ("expenses:read", "expenses:write")),
        (ROLE_AUDITOR, ("expenses:read",)),
        (ROLE_FINANCIAL_ANALYST, ("expenses:read",)),
    ]
    for role_id, codes in grants:
        code_list = ", ".join(f"'{c}'" for c in codes)
        op.execute(
            f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT '{role_id}', id FROM permissions WHERE code IN ({code_list})
            ON CONFLICT DO NOTHING;
            """
        )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN ('expenses:read', 'expenses:write', 'expenses:approve')
        );
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN ('expenses:read', 'expenses:write', 'expenses:approve');
        """
    )
