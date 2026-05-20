"""seed_mail_gateway_config

Revision ID: 20260520_010b
Revises: 20260520_010

Seed mailboxes per `06` §19.7. Passwords encrypted with FINANCE_PRIVACY_ENCRYPTION_KEY.
Dev default password: dev-mailbox-not-configured (rotate via Client Admin UI).
"""

import os

from alembic import op
import sqlalchemy as sa

revision = "20260520_010b"
down_revision = "20260520_010"
branch_labels = None
depends_on = None

MAILBOX_ACC_MANAGER = "00000000-0000-0000-0000-000000000201"
MAILBOX_ACCAR = "00000000-0000-0000-0000-000000000202"
MAILBOX_ACCAP = "00000000-0000-0000-0000-000000000203"
MAILBOX_ACCEXP = "00000000-0000-0000-0000-000000000204"
MAILBOX_FINTREASURY = "00000000-0000-0000-0000-000000000205"
MAILBOX_FINFA = "00000000-0000-0000-0000-000000000206"
MAILBOX_FIN_MANAGER = "00000000-0000-0000-0000-000000000207"
MAILBOX_CFO = "00000000-0000-0000-0000-000000000208"
MAILBOX_CEO = "00000000-0000-0000-0000-000000000209"


# Encrypted "dev-mailbox-not-configured" for bootstrap when .env has placeholder keys.
_DEV_PASSWORD_ENCRYPTED = (
    "gAAAAABqDSEv1kolsvVmAImq7uCpwhSbV5_Zvgj7x3evhhiZoO3L9QlqG95OlkGMNUk3CVmVNhuRJJ3S4sM_NGhffo86Bc1g3JjwNoxGRxDvobqQ33rloJA="
)


def _encrypted_password() -> str:
    key = os.environ.get("FINANCE_PRIVACY_ENCRYPTION_KEY", "").strip()
    if not key or key.startswith("["):
        return _DEV_PASSWORD_ENCRYPTED
    from app.core.crypto import encrypt_field

    raw = os.environ.get("FINANCE_MAIL_SEED_PASSWORD", "dev-mailbox-not-configured")
    return encrypt_field(raw)


def upgrade() -> None:
    password_encrypted = _encrypted_password()
    conn = op.get_bind()
    rows = [
        (
            MAILBOX_ACC_MANAGER,
            "acc.mmlogistix@bp0.work",
            "mmlogistix Manager Accounts",
            "Manager Accounts",
            "manager_human",
            "cfo.mmlogistix@bp0.work",
            None,
            True,
        ),
        (
            MAILBOX_ACCAR,
            "accar.mmlogistix@bp0.work",
            "mmlogistix Account Receivables Executive",
            "AR Executive",
            "executive_agent",
            "acc.mmlogistix@bp0.work",
            "ar_invoice",
            True,
        ),
        (
            MAILBOX_ACCAP,
            "accap.mmlogistix@bp0.work",
            "mmlogistix Account Payables Executive",
            "AP Executive",
            "executive_agent",
            "acc.mmlogistix@bp0.work",
            "ap_invoice",
            False,
        ),
        (
            MAILBOX_ACCEXP,
            "accexp.mmlogistix@bp0.work",
            "mmlogistix Expense Management Executive",
            "Expense Executive",
            "executive_agent",
            "acc.mmlogistix@bp0.work",
            None,
            False,
        ),
        (
            MAILBOX_FINTREASURY,
            "fintreasury.mmlogistix@bp0.work",
            "mmlogistix Treasury Executive",
            "Treasury Executive",
            "executive_agent",
            "fin.mmlogistix@bp0.work",
            "treasury_reconciliation",
            False,
        ),
        (
            MAILBOX_FINFA,
            "finfa.mmlogistix@bp0.work",
            "mmlogistix Financial Reporting Executive",
            "Financial Reporting Executive",
            "executive_agent",
            "fin.mmlogistix@bp0.work",
            None,
            False,
        ),
        (
            MAILBOX_FIN_MANAGER,
            "fin.mmlogistix@bp0.work",
            "mmlogistix Manager Finance",
            "Manager Finance",
            "manager_human",
            "cfo.mmlogistix@bp0.work",
            None,
            True,
        ),
        (
            MAILBOX_CFO,
            "cfo.mmlogistix@bp0.work",
            "mmlogistix CFO / Finance Director",
            "CFO / Finance Director",
            "manager_human",
            "ceo.mmlogistix@bp0.work",
            None,
            True,
        ),
        (
            MAILBOX_CEO,
            "ceo.mmlogistix@bp0.work",
            "mmlogistix CEO / Managing Director",
            "CEO / Managing Director",
            "manager_human",
            None,
            None,
            True,
        ),
    ]
    for (
        mailbox_id,
        email_address,
        display_name,
        role,
        mailbox_mode,
        escalation,
        default_case_type,
        is_active,
    ) in rows:
        case_type_sql = (
            f"'{default_case_type}'::case_type" if default_case_type else "NULL"
        )
        conn.execute(
            sa.text(f"""
            INSERT INTO mail_gateway_config (
                id, email_address, display_name, role, mailbox_mode,
                escalation_manager_email, server_host, server_port, use_ssl,
                username, password_encrypted, poll_interval_seconds, is_active,
                default_case_type
            ) VALUES (
                :id, :email_address, :display_name, :role, :mailbox_mode,
                :escalation, 'bp0.work', 993, true,
                :email_address, :password_encrypted, 60, :is_active,
                {case_type_sql}
            )
            ON CONFLICT (email_address) DO NOTHING;
            """),
            {
                "id": mailbox_id,
                "email_address": email_address,
                "display_name": display_name,
                "role": role,
                "mailbox_mode": mailbox_mode,
                "escalation": escalation,
                "password_encrypted": password_encrypted,
                "is_active": is_active,
            },
        )


def downgrade() -> None:
    ids = ", ".join(
        f"'{uid}'"
        for uid in (
            MAILBOX_ACC_MANAGER,
            MAILBOX_ACCAR,
            MAILBOX_ACCAP,
            MAILBOX_ACCEXP,
            MAILBOX_FINTREASURY,
            MAILBOX_FINFA,
            MAILBOX_FIN_MANAGER,
            MAILBOX_CFO,
            MAILBOX_CEO,
        )
    )
    op.execute(sa.text(f"DELETE FROM mail_gateway_config WHERE id IN ({ids});"))
