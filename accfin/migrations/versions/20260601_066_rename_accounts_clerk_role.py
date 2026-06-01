"""rename_accounts_clerk_to_accounts_manager — role rename + ca_*@example.com test user cleanup."""

from alembic import op
import sqlalchemy as sa

revision = "20260601_066"
down_revision = "90f9fdae291d"
branch_labels = None
depends_on = None

ROLE_ACCOUNTS_MANAGER_ID = "00000000-0000-0000-0000-000000000005"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        DELETE FROM refresh_tokens
        WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'ca_%@example.com');
        """)
    )
    conn.execute(
        sa.text("""
        DELETE FROM password_history
        WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'ca_%@example.com');
        """)
    )
    conn.execute(
        sa.text("""
        DELETE FROM users WHERE email LIKE 'ca_%@example.com';
        """)
    )
    conn.execute(
        sa.text("""
        UPDATE roles
        SET name = 'accounts_manager',
            display_name = 'Accounts Manager',
            description = 'Accounts management and tier-2 case processing'
        WHERE id = :role_id AND name = 'accounts_clerk';
        """),
        {"role_id": ROLE_ACCOUNTS_MANAGER_ID},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        UPDATE roles
        SET name = 'accounts_clerk',
            display_name = 'Accounts Clerk',
            description = 'Case creation and data entry'
        WHERE id = :role_id AND name = 'accounts_manager';
        """),
        {"role_id": ROLE_ACCOUNTS_MANAGER_ID},
    )
