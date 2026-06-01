"""Roles allowed to use finance-ui setup screens (counterparty, agreements, GL calendar)."""

from __future__ import annotations

FINANCE_SETUP_ROLE_NAMES = frozenset(
    {
        "client_admin",
        "general_manager",
        "cfo",
        "finance_manager",
        "accounts_manager",
        "financial_analyst",
        "ar_executive",
        "ap_executive",
    }
)
