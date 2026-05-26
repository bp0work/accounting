"""Client Admin catalog keys and role ordering."""

from __future__ import annotations

TRAVEL_EXPENSE_POLICY_KEY = "travel_expense_policy"
TRAVEL_EXPENSE_POLICY_LABEL = "Travel & Entertainment"

# Bootstrap password for provisioned key-role users (rotate before login).
BOOTSTRAP_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$gnlhsND5BlHE/sF7f/hVoA$"
    "ZleXPrKHMAWstqbXATdCbmttGkmSbcbBugFf80fQTFw"
)

ROLE_PROVISION: dict[str, tuple[str, str]] = {
    "general_manager": ("ceo.mmlogistix", "00000000-0000-0000-0000-000000000104"),
    "cfo": ("cfo.mmlogistix", "00000000-0000-0000-0000-000000000102"),
    "finance_manager": ("finmanager.mmlogistix", "00000000-0000-0000-0000-000000000103"),
    "accounts_clerk": ("acc.mmlogistix", "00000000-0000-0000-0000-000000000105"),
}

REGULATORY_CATALOG: list[tuple[str, str, str]] = [
    ("mas_trm_2021", "MAS TRM 2021", "transactions/regulatory/mas-trm-2021.pdf"),
    ("pdpa_2020", "PDPA 2020", "transactions/regulatory/pdpa-2020.pdf"),
    ("companies_act", "Companies Act", "transactions/regulatory/companies-act.pdf"),
    ("iras_gst", "IRAS GST Guide", "transactions/regulatory/iras-gst-guide.pdf"),
    ("income_tax_act", "Income Tax Act", "transactions/regulatory/income-tax-act.pdf"),
]

ROLE_ORDER: list[tuple[str, str]] = [
    ("general_manager", "CEO / Managing Director"),
    ("cfo", "CFO / Finance Director"),
    ("finance_manager", "Finance Manager (fin)"),
    ("accounts_clerk", "Accounts Manager (acc)"),
]

ROLE_ADMIN_NAMES = tuple(r[0] for r in ROLE_ORDER)
