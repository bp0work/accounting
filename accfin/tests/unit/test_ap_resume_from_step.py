"""Unit tests — AP manual retry resume_from_step mapping."""

from unittest.mock import MagicMock

from app.models.case import Case
from workers.ap.handlers import (
    REASON_TO_RESUME_STEP,
    _pop_resume_from_step,
    _resume_step_reached,
    _REASON_COA_NOT_FOUND,
    _REASON_CURRENCY_CONVERSION,
    _REASON_DUPLICATE,
    _REASON_VENDOR_NOT_FOUND,
)


def test_reason_to_resume_step_mapping():
    assert REASON_TO_RESUME_STEP[_REASON_VENDOR_NOT_FOUND] == "2C"
    assert REASON_TO_RESUME_STEP[_REASON_DUPLICATE] == "2B"
    assert REASON_TO_RESUME_STEP[_REASON_COA_NOT_FOUND] == "2G"


def test_resume_step_reached_skips_preceding():
    assert _resume_step_reached("2C", "2A") is False
    assert _resume_step_reached("2C", "2B") is False
    assert _resume_step_reached("2C", "2C") is True
    assert _resume_step_reached("2C", "2G") is True
    assert _resume_step_reached(None, "2A") is True


def test_pop_resume_from_step_clears_metadata():
    case = Case(
        case_number="CAS-TEST-1",
        type="ap_invoice",
        status="classified",
        subject="Test",
        amount_currency="SGD",
        workflow_metadata={
            "resume_from_step": "2D",
            "extracted_fields": {"vendor_name": "ACME"},
        },
    )
    step = _pop_resume_from_step(case)
    assert step == "2D"
    assert "resume_from_step" not in (case.workflow_metadata or {})
    assert case.workflow_metadata["extracted_fields"]["vendor_name"] == "ACME"


def test_pop_resume_from_step_none_when_missing():
    case = MagicMock()
    case.workflow_metadata = {}
    assert _pop_resume_from_step(case) is None
