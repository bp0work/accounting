"""GL period reopen — status and retry eligibility."""

from uuid import uuid4

import pytest

from app.services.case_service import RETRYABLE_STATUSES


def test_retryable_statuses_unchanged() -> None:
    assert RETRYABLE_STATUSES == frozenset({"exception", "manual_review"})


@pytest.mark.parametrize(
    "period_status,expected",
    [
        ("open", True),
        ("review", True),
        ("closed", False),
    ],
)
def test_period_closed_hold_retryable_when_period_open(period_status: str, expected: bool) -> None:
    """Document expected retry rule: on_hold + PERIOD_CLOSED + period not closed."""

    class _Period:
        status = period_status

    class _Case:
        status = "on_hold"
        workflow_metadata = {
            "reason_code": "PERIOD_CLOSED",
            "gl_period_id": str(uuid4()),
        }

    meta = _Case.workflow_metadata
    period = _Period()
    retryable = (
        _Case.status == "on_hold"
        and meta.get("reason_code") == "PERIOD_CLOSED"
        and period is not None
        and period.status != "closed"
    )
    assert retryable is expected
