"""seed_roles_and_permissions

Revision ID: 20260510_006
Revises: 20260510_005

Seed data: 06_Database_Schema_Design.md §19.1–§19.3
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260510_006"
down_revision = "20260510_005"
branch_labels = None
depends_on = None

ROLE_PLATFORM_ADMIN = "00000000-0000-0000-0000-000000000001"
ROLE_CLIENT_ADMIN = "00000000-0000-0000-0000-000000000008"
ROLE_CFO = "00000000-0000-0000-0000-000000000002"
ROLE_FINANCE_MANAGER = "00000000-0000-0000-0000-000000000003"
ROLE_FINANCE_OFFICER = "00000000-0000-0000-0000-000000000004"
ROLE_ACCOUNTS_CLERK = "00000000-0000-0000-0000-000000000005"
ROLE_AUDITOR = "00000000-0000-0000-0000-000000000006"
ROLE_GENERAL_MANAGER = "00000000-0000-0000-0000-000000000007"
ROLE_FINANCIAL_ANALYST = "00000000-0000-0000-0000-000000000009"


def upgrade() -> None:
    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=False)),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_system", sa.Boolean),
    )

    op.bulk_insert(
        roles_table,
        [
            {
                "id": ROLE_PLATFORM_ADMIN,
                "name": "platform_admin",
                "display_name": "Platform Administrator",
                "description": "bp0 operator — platform scope (system@bp0.work)",
                "is_system": True,
            },
            {
                "id": ROLE_CLIENT_ADMIN,
                "name": "client_admin",
                "display_name": "Client System Administrator",
                "description": "Tenant operator — mailboxes, COA, tenant settings",
                "is_system": True,
            },
            {
                "id": ROLE_CFO,
                "name": "cfo",
                "display_name": "Chief Financial Officer",
                "description": "Tier 3 financial approvals and oversight",
                "is_system": True,
            },
            {
                "id": ROLE_FINANCE_MANAGER,
                "name": "finance_manager",
                "display_name": "Finance Manager",
                "description": "Tier 2 approvals and team management",
                "is_system": True,
            },
            {
                "id": ROLE_FINANCE_OFFICER,
                "name": "finance_officer",
                "display_name": "Finance Officer",
                "description": "Tier 2 approvals and case processing",
                "is_system": True,
            },
            {
                "id": ROLE_ACCOUNTS_CLERK,
                "name": "accounts_clerk",
                "display_name": "Accounts Clerk",
                "description": "Case creation and data entry",
                "is_system": True,
            },
            {
                "id": ROLE_AUDITOR,
                "name": "auditor",
                "display_name": "Auditor",
                "description": "Read-only audit and compliance access",
                "is_system": True,
            },
            {
                "id": ROLE_GENERAL_MANAGER,
                "name": "general_manager",
                "display_name": "General Manager",
                "description": "Operational workflows — outside financial approval hierarchy",
                "is_system": True,
            },
            {
                "id": ROLE_FINANCIAL_ANALYST,
                "name": "financial_analyst",
                "display_name": "Financial Analyst",
                "description": "Analysis, financial statements, month-end close",
                "is_system": True,
            },
        ],
    )

    op.execute(
        sa.text("""
        INSERT INTO permissions (code, category, action, description) VALUES
        ('cases:read', 'cases', 'read', 'View cases and case details'),
        ('cases:write', 'cases', 'write', 'Create and update cases'),
        ('cases:delete', 'cases', 'delete', 'Delete cases'),
        ('approvals:read', 'approvals', 'read', 'View approval requests and history'),
        ('approvals:approve', 'approvals', 'approve', 'Approve or reject approval requests'),
        ('approvals:admin', 'approvals', 'admin', 'Override approvals, manage approval rules'),
        ('journal-entries:read', 'journal_entries', 'read', 'View journal entries'),
        ('journal-entries:write', 'journal_entries', 'write', 'Create and post journal entries'),
        ('policies:read', 'policies', 'read', 'View accounting and workflow policies'),
        ('policies:write', 'policies', 'write', 'Create and update policies'),
        ('queues:read', 'queues', 'read', 'View queue status and messages'),
        ('queues:admin', 'queues', 'admin', 'Manage queue messages, retry, purge'),
        ('reconciliation:read', 'reconciliation', 'read', 'View reconciliation data'),
        ('reconciliation:write', 'reconciliation', 'write', 'Perform reconciliations, match/unmatch'),
        ('audit-logs:read', 'audit_logs', 'read', 'View audit logs'),
        ('users:read', 'users', 'read', 'View users'),
        ('users:write', 'users', 'write', 'Create and update users'),
        ('users:admin', 'users', 'admin', 'Full user management including password resets'),
        ('settings:read', 'settings', 'read', 'View system settings'),
        ('settings:write', 'settings', 'write', 'Modify system settings'),
        ('mail:read', 'mail', 'read', 'View mail gateway messages and logs'),
        ('mail:admin', 'mail', 'admin', 'Manage mail gateway configuration'),
        ('platform:admin', 'platform', 'admin', 'Platform-scoped configuration and Client Admin identity'),
        ('tenant:admin', 'tenant', 'admin', 'Tenant-scoped operational administration'),
        ('coa:import', 'coa', 'import', 'Bulk chart of accounts upload'),
        ('reports:read', 'reports', 'read', 'View financial reports and statements'),
        ('month-end:read', 'month_end', 'read', 'View month-end close checklist and period status'),
        ('month-end:write', 'month_end', 'write', 'Execute month-end close procedures and period adjustments')
        ON CONFLICT (code) DO NOTHING;
    """)
    )

    role_perm_sql = [
        (
            ROLE_PLATFORM_ADMIN,
            "('platform:admin', 'users:read', 'users:admin', 'audit-logs:read')",
        ),
        (
            ROLE_CLIENT_ADMIN,
            "('tenant:admin', 'mail:read', 'mail:admin', 'settings:read', 'settings:write', 'coa:import')",
        ),
        (
            ROLE_CFO,
            """('cases:read', 'cases:write', 'approvals:read', 'approvals:approve', 'approvals:admin',
            'journal-entries:read', 'journal-entries:write', 'policies:read', 'policies:write',
            'queues:read', 'reconciliation:read', 'reconciliation:write', 'audit-logs:read',
            'users:read', 'settings:read', 'settings:write', 'mail:read')""",
        ),
        (
            ROLE_FINANCE_MANAGER,
            """('cases:read', 'cases:write', 'approvals:read', 'approvals:approve',
            'journal-entries:read', 'journal-entries:write', 'policies:read', 'queues:read',
            'reconciliation:read', 'reconciliation:write', 'audit-logs:read',
            'users:read', 'users:write', 'settings:read', 'mail:read')""",
        ),
        (
            ROLE_FINANCE_OFFICER,
            """('cases:read', 'cases:write', 'approvals:read', 'approvals:approve',
            'journal-entries:read', 'journal-entries:write', 'policies:read', 'queues:read',
            'reconciliation:read', 'reconciliation:write', 'mail:read')""",
        ),
        (
            ROLE_ACCOUNTS_CLERK,
            "('cases:read', 'cases:write', 'journal-entries:read', 'reconciliation:read', 'mail:read')",
        ),
        (
            ROLE_FINANCIAL_ANALYST,
            """('cases:read', 'journal-entries:read', 'journal-entries:write', 'policies:read',
            'queues:read', 'reconciliation:read', 'reconciliation:write', 'audit-logs:read',
            'mail:read', 'reports:read', 'month-end:read', 'month-end:write')""",
        ),
        (
            ROLE_AUDITOR,
            """('cases:read', 'approvals:read', 'journal-entries:read', 'policies:read',
            'reconciliation:read', 'audit-logs:read', 'users:read', 'mail:read')""",
        ),
        (
            ROLE_GENERAL_MANAGER,
            "('cases:read', 'cases:write', 'approvals:read', 'queues:read', 'mail:read')",
        ),
    ]

    for role_id, codes in role_perm_sql:
        op.execute(
            sa.text(f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT '{role_id}', id FROM permissions
            WHERE code IN {codes}
            ON CONFLICT DO NOTHING;
        """)
        )


def downgrade() -> None:
    role_ids = (
        ROLE_PLATFORM_ADMIN,
        ROLE_CLIENT_ADMIN,
        ROLE_CFO,
        ROLE_FINANCE_MANAGER,
        ROLE_FINANCE_OFFICER,
        ROLE_ACCOUNTS_CLERK,
        ROLE_AUDITOR,
        ROLE_GENERAL_MANAGER,
        ROLE_FINANCIAL_ANALYST,
    )
    op.execute(
        sa.text(f"""
        DELETE FROM role_permissions
        WHERE role_id IN ({",".join(f"'{r}'" for r in role_ids)});
    """)
    )
    op.execute(
        sa.text("""
        DELETE FROM permissions WHERE code IN (
            'cases:read', 'cases:write', 'cases:delete',
            'approvals:read', 'approvals:approve', 'approvals:admin',
            'journal-entries:read', 'journal-entries:write',
            'policies:read', 'policies:write',
            'queues:read', 'queues:admin',
            'reconciliation:read', 'reconciliation:write',
            'audit-logs:read',
            'users:read', 'users:write', 'users:admin',
            'settings:read', 'settings:write',
            'mail:read', 'mail:admin',
            'platform:admin', 'tenant:admin', 'coa:import',
            'reports:read', 'month-end:read', 'month-end:write'
        );
    """)
    )
    op.execute(
        sa.text(f"""
        DELETE FROM roles WHERE id IN ({",".join(f"'{r}'" for r in role_ids)});
    """)
    )
