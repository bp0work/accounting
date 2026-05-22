"""seed_mmlogistix_finance_users

Revision ID: 20260523_047
Revises: 20260529_046

Seed CFO and Finance Manager users for mmlogistix tenant (finance oversight UI).
Dev password: ChangeMeOnFirstLogin! — rotate on first login.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260523_047"
down_revision = "20260529_046"
branch_labels = None
depends_on = None

TENANT_MMLOGISTIX = "00000000-0000-0000-0000-000000000200"
USER_CFO = "00000000-0000-0000-0000-000000000102"
USER_FINANCE_MANAGER = "00000000-0000-0000-0000-000000000103"
ROLE_CFO = "00000000-0000-0000-0000-000000000002"
ROLE_FINANCE_MANAGER = "00000000-0000-0000-0000-000000000003"

# Argon2id hash of "ChangeMeOnFirstLogin!" — same as 006c_seed_system_admin_users
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
        ) VALUES
            (
                :cfo_id, 'cfo.mmlogistix', 'mmlogistix CFO',
                'cfo.mmlogistix@bp0.work', :password_hash,
                :cfo_role, :tenant_id, 'active', false
            ),
            (
                :fin_mgr_id, 'finmanager.mmlogistix', 'mmlogistix Finance Manager',
                'fin.mmlogistix@bp0.work', :password_hash,
                :fin_mgr_role, :tenant_id, 'active', false
            )
        ON CONFLICT (id) DO NOTHING;
        """),
        {
            "cfo_id": USER_CFO,
            "fin_mgr_id": USER_FINANCE_MANAGER,
            "password_hash": DEV_PASSWORD_HASH,
            "cfo_role": ROLE_CFO,
            "fin_mgr_role": ROLE_FINANCE_MANAGER,
            "tenant_id": TENANT_MMLOGISTIX,
        },
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
        DELETE FROM users
        WHERE id IN ('{USER_CFO}', '{USER_FINANCE_MANAGER}');
        """)
    )
