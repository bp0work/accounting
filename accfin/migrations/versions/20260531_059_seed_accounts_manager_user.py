"""seed_accounts_manager_user — provision accounts_manager (Manager Accounts) login."""

from alembic import op
import sqlalchemy as sa

revision = "20260531_059"
down_revision = "20260531_058"
branch_labels = None
depends_on = None

TENANT_MMLOGISTIX = "00000000-0000-0000-0000-000000000200"
USER_ACCOUNTS_MANAGER = "00000000-0000-0000-0000-000000000105"
ROLE_ACCOUNTS_MANAGER = "00000000-0000-0000-0000-000000000005"
DEV_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$gnlhsND5BlHE/sF7f/hVoA$"
    "ZleXPrKHMAWstqbXATdCbmttGkmSbcbBugFf80fQTFw"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        INSERT INTO users (
            id, username, display_name, email, password_hash,
            role_id, tenant_id, status, two_factor_enabled
        ) VALUES (
            :user_id, 'acc.mmlogistix', 'mmlogistix Accounts Manager',
            'acc.mmlogistix@bp0.work', :password_hash,
            :role_id, :tenant_id, 'active', false
        ) ON CONFLICT (id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            email = EXCLUDED.email,
            role_id = EXCLUDED.role_id,
            tenant_id = EXCLUDED.tenant_id,
            status = 'active';
        """),
        {
            "user_id": USER_ACCOUNTS_MANAGER,
            "password_hash": DEV_PASSWORD_HASH,
            "role_id": ROLE_ACCOUNTS_MANAGER,
            "tenant_id": TENANT_MMLOGISTIX,
        },
    )


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM users WHERE id = '{USER_ACCOUNTS_MANAGER}';"))
