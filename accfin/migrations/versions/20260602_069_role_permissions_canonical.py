"""role_permissions_canonical — `0.15.04-role-permissions-migration`.

Idempotent role rename (if 066 not applied), canonical role_permissions for
accounts_manager / finance_manager / cfo, user role fixes, test user cleanup.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260602_069"
down_revision = "20260602_067"
branch_labels = None
depends_on = None

ACCOUNTS_MANAGER_PERMISSIONS = (
    "approvals:approve",
    "approvals:read",
    "audit-logs:read",
    "cases:read",
    "cases:write",
    "expenses:approve",
    "expenses:read",
    "expenses:write",
    "journal-entries:read",
    "journal-entries:write",
    "mail:read",
    "policies:read",
    "queues:read",
    "reconciliation:read",
    "reconciliation:write",
    "settings:read",
    "users:read",
)

FINANCE_MANAGER_PERMISSIONS = (
    "approvals:read",
    "audit-logs:read",
    "cases:read",
    "expenses:read",
    "journal-entries:read",
    "reconciliation:read",
    "reports:read",
    "settings:read",
    "users:read",
)

CFO_PERMISSIONS = (
    "approvals:admin",
    "approvals:approve",
    "approvals:read",
    "audit-logs:read",
    "cases:read",
    "cases:write",
    "expenses:approve",
    "expenses:read",
    "expenses:write",
    "journal-entries:read",
    "journal-entries:write",
    "mail:read",
    "policies:read",
    "policies:write",
    "queues:read",
    "reconciliation:read",
    "reconciliation:write",
    "reports:read",
    "settings:read",
    "settings:write",
    "users:read",
)


def _code_list(codes: tuple[str, ...]) -> str:
    return ", ".join(f"'{code}'" for code in codes)


def _reset_role_permissions(conn, role_name: str, codes: tuple[str, ...]) -> None:
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id = (SELECT id FROM roles WHERE name = :role_name)
            """
        ),
        {"role_name": role_name},
    )
    conn.execute(
        sa.text(
            f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.name = :role_name
              AND p.code IN ({_code_list(codes)})
            ON CONFLICT DO NOTHING
            """
        ),
        {"role_name": role_name},
    )


def _delete_users_by_email_pattern(conn, pattern: str) -> None:
    conn.execute(
        sa.text(
            """
            DELETE FROM refresh_tokens
            WHERE user_id IN (SELECT id FROM users WHERE email LIKE :pattern)
            """
        ),
        {"pattern": pattern},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM password_history
            WHERE user_id IN (SELECT id FROM users WHERE email LIKE :pattern)
            """
        ),
        {"pattern": pattern},
    )
    conn.execute(
        sa.text("DELETE FROM users WHERE email LIKE :pattern"),
        {"pattern": pattern},
    )


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE roles
            SET name = 'accounts_manager',
                display_name = 'Accounts Manager',
                description = 'Accounts management and tier-2 case processing'
            WHERE name = 'accounts_clerk'
            """
        )
    )

    _reset_role_permissions(conn, "accounts_manager", ACCOUNTS_MANAGER_PERMISSIONS)
    _reset_role_permissions(conn, "finance_manager", FINANCE_MANAGER_PERMISSIONS)
    _reset_role_permissions(conn, "cfo", CFO_PERMISSIONS)

    conn.execute(
        sa.text(
            """
            UPDATE users
            SET role_id = (SELECT id FROM roles WHERE name = 'accounts_manager')
            WHERE username = 'acc.mmlogistix'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE users
            SET role_id = (SELECT id FROM roles WHERE name = 'finance_manager')
            WHERE username IN ('fin.mmlogistix', 'finmanager.mmlogistix')
            """
        )
    )

    _delete_users_by_email_pattern(conn, "%@example.com")


def downgrade() -> None:
    # Canonical permission reset is not safely reversible — re-apply from 006/043 seeds manually.
    pass
