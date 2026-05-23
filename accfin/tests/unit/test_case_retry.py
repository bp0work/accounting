"""Unit tests for case retry eligibility."""

from app.services.case_service import RETRYABLE_STATUSES


def test_retryable_statuses() -> None:
    assert RETRYABLE_STATUSES == frozenset({"exception", "manual_review"})
