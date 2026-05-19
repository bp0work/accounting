"""seed_system_admin_users

Revision ID: 20260510_006c
Revises: 20260510_006b

Seed: 06_Database_Schema_Design.md §19.8
Dev password: ChangeMeOnFirstLogin! (rotate on first login)
"""

from alembic import op
import sqlalchemy as sa

revision = "20260510_006c"
down_revision = "20260510_006b"
branch_labels = None
depends_on = None

USER_PLATFORM_ADMIN = "00000000-0000-0000-0000-000000000100"
USER_CLIENT_ADMIN = "00000000-0000-0000-0000-000000000101"
ROLE_PLATFORM_ADMIN = "00000000-0000-0000-0000-000000000001"
ROLE_CLIENT_ADMIN = "00000000-0000-0000-0000-000000000008"

# Argon2id hash of "ChangeMeOnFirstLogin!" — rotate on first login
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
            role_id, status, two_factor_enabled
        ) VALUES
            (
                :platform_id, 'system', 'BP0 Platform Administrator',
                'system@bp0.work', :password_hash, :platform_role, 'active', false
            ),
            (
                :client_id, 'system.mmlogistix', 'mmlogistix System Administrator',
                'system.mmlogistix@bp0.work', :password_hash, :client_role, 'active', false
            )
        ON CONFLICT (id) DO NOTHING;
        """),
        {
            "platform_id": USER_PLATFORM_ADMIN,
            "client_id": USER_CLIENT_ADMIN,
            "password_hash": DEV_PASSWORD_HASH,
            "platform_role": ROLE_PLATFORM_ADMIN,
            "client_role": ROLE_CLIENT_ADMIN,
        },
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
        DELETE FROM users WHERE id IN ('{USER_PLATFORM_ADMIN}', '{USER_CLIENT_ADMIN}');
    """)
    )
