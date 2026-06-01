"""Unit tests — manual review escalation API role gate."""

from app.core.dependencies import MANUAL_REVIEW_ESCALATION_ROLES


def test_manual_review_escalation_roles() -> None:
    assert MANUAL_REVIEW_ESCALATION_ROLES == frozenset(
        {"accounts_manager", "finance_manager", "cfo"}
    )
