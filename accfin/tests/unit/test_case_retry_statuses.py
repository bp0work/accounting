"""Case retry — retryable status set."""

from app.services.case_retry import RETRYABLE_STATUSES


def test_classified_is_retryable() -> None:
    assert "classified" in RETRYABLE_STATUSES
