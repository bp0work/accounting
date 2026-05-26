"""remove_seed_coa_accounts — drop demo COA rows; tenant imports own chart via Client Admin."""

from alembic import op

revision = "20260531_054"
down_revision = "20260531_053"
branch_labels = None
depends_on = None

# Seeded in 20260523_027 and 20260524_026b for dev demos — not used in production.
SEED_ACCOUNT_CODES = (
    "1200",
    "1300",
    "2000",
    "2100",
    "4100",
    "5200",
    "5500",
    "1190",
)


def upgrade() -> None:
    codes = ", ".join(f"'{c}'" for c in SEED_ACCOUNT_CODES)
    op.execute(
        f"""
        DELETE FROM coa_accounts c
        WHERE c.account_code IN ({codes})
          AND NOT EXISTS (
              SELECT 1 FROM journal_entry_lines j WHERE j.account_id = c.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM expense_line_items e WHERE e.gl_account_id = c.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM reconciliation_runs r WHERE r.account_id = c.id
          );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO coa_accounts (account_code, account_name, account_type, is_bank_account)
        VALUES
            ('1200', 'Bank — DBS Operating', 'asset', true),
            ('1300', 'Accounts Receivable', 'asset', false),
            ('2100', 'GST Payable', 'liability', false),
            ('4100', 'Sales Revenue', 'revenue', false),
            ('5200', 'Discount Allowed', 'expense', false)
        ON CONFLICT (account_code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO coa_accounts (account_code, account_name, account_type)
        VALUES
            ('2000', 'Trade Creditors', 'liability'),
            ('5500', 'Operating Expenses', 'expense'),
            ('1190', 'GST Input Tax', 'asset')
        ON CONFLICT (account_code) DO NOTHING;
        """
    )
