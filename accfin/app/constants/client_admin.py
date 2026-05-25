"""Client Admin catalog keys and role ordering."""

from __future__ import annotations

TRAVEL_EXPENSE_POLICY_KEY = "travel_expense_policy"
TRAVEL_EXPENSE_POLICY_LABEL = "Travel & Expense Policy"

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
