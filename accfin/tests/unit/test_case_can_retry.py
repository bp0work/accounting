"""Unit tests — case_can_manual_retry for Finance UI."""

from app.models.case import Case
from app.services.case_retry import case_can_manual_retry


def test_manual_review_can_retry():
    case = Case(
        case_number="CAS-T-1",
        type="ap_invoice",
        status="manual_review",
        subject="x",
        workflow_metadata={"reason_code": "AP_PARSING_INCOMPLETE"},
    )
    assert case_can_manual_retry(case) is True


def test_on_hold_hermes_in_error_reason_blob():
    case = Case(
        case_number="CAS-T-2",
        type="ap_invoice",
        status="on_hold",
        subject="x",
        workflow_metadata={
            "error_reason": "Worker processing error — HERMES_TIMEOUT: ",
            "escalation_pending": True,
        },
    )
    assert case_can_manual_retry(case) is True


def test_on_hold_period_closed_not_retryable_when_still_closed():
    case = Case(
        case_number="CAS-T-3",
        type="ap_invoice",
        status="on_hold",
        subject="x",
        workflow_metadata={"reason_code": "PERIOD_CLOSED", "gl_period_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert case_can_manual_retry(case, linked_gl_period_status="closed") is False


def test_posted_cannot_retry():
    case = Case(
        case_number="CAS-T-4",
        type="ap_invoice",
        status="posted",
        subject="x",
    )
    assert case_can_manual_retry(case) is False
