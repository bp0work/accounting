"""client_admin_seed — tenant profile, role emails, CEO user, accounting settings."""

from alembic import op
import sqlalchemy as sa

revision = "20260531_050"
down_revision = "20260531_049"
branch_labels = None
depends_on = None

TENANT_MMLOGISTIX = "00000000-0000-0000-0000-000000000200"
USER_CEO = "00000000-0000-0000-0000-000000000104"
ROLE_GENERAL_MANAGER = "00000000-0000-0000-0000-000000000007"
DEV_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$gnlhsND5BlHE/sF7f/hVoA$"
    "ZleXPrKHMAWstqbXATdCbmttGkmSbcbBugFf80fQTFw"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        INSERT INTO tenant_profiles (
            tenant_id, legal_name, trading_name, uen, contact_email, registered_address
        ) VALUES (
            :tenant_id, 'MMLOGISTIX PTE. LTD.', 'mmlogistix',
            NULL, 'acc.mmlogistix@bp0.work', 'Singapore'
        ) ON CONFLICT (tenant_id) DO NOTHING;
        """),
        {"tenant_id": TENANT_MMLOGISTIX},
    )
    conn.execute(
        sa.text("""
        INSERT INTO users (
            id, username, display_name, email, password_hash,
            role_id, tenant_id, status, two_factor_enabled
        ) VALUES (
            :ceo_id, 'ceo.mmlogistix', 'mmlogistix CEO / Managing Director',
            'ceo.mmlogistix@bp0.work', :password_hash,
            :role_id, :tenant_id, 'active', false
        ) ON CONFLICT (id) DO UPDATE SET
            email = EXCLUDED.email,
            display_name = EXCLUDED.display_name;
        """),
        {
            "ceo_id": USER_CEO,
            "password_hash": DEV_PASSWORD_HASH,
            "role_id": ROLE_GENERAL_MANAGER,
            "tenant_id": TENANT_MMLOGISTIX,
        },
    )
    conn.execute(
        sa.text("""
        UPDATE users SET email = 'cfo.mmlogistix@bp0.work'
        WHERE username = 'cfo.mmlogistix';
        UPDATE users SET email = 'fin.mmlogistix@bp0.work'
        WHERE username IN ('finmanager.mmlogistix', 'fin.mmlogistix');
        UPDATE users SET tenant_id = :tenant_id
        WHERE username = 'system.mmlogistix' AND tenant_id IS NULL;
        """),
        {"tenant_id": TENANT_MMLOGISTIX},
    )
    conn.execute(
        sa.text("""
        INSERT INTO system_settings (key, value, value_type, description, category)
        VALUES (
            'gl_posting_cutoff_working_days', '3', 'integer',
            'Working days after month end before GL cutoff date', 'accounting'
        ) ON CONFLICT (key) DO NOTHING;
        """)
    )


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM users WHERE id = '{USER_CEO}';"))
    op.execute(sa.text(f"DELETE FROM tenant_profiles WHERE tenant_id = '{TENANT_MMLOGISTIX}';"))
    op.execute(sa.text("DELETE FROM system_settings WHERE key = 'gl_posting_cutoff_working_days';"))
