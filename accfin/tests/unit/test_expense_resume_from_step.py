"""Expense worker resume step mapping — `0.14.45-expense-workflow`."""

from workers.expense.handlers import (
    REASON_TO_RESUME_STEP,
    _REASON_COA,
    _REASON_CURRENCY,
    _REASON_DUPLICATE,
    _REASON_PARSING,
    _REASON_POLICY,
    _REASON_RECEIPT,
    _REASON_SUBMITTER_INACTIVE,
    _REASON_SUBMITTER_NOT_FOUND,
    _pop_resume_from_step,
    _resume_step_reached,
)
from types import SimpleNamespace


def test_expense_reason_to_resume_step() -> None:
    assert REASON_TO_RESUME_STEP[_REASON_PARSING] == "2A"
    assert REASON_TO_RESUME_STEP[_REASON_DUPLICATE] == "2B"
    assert REASON_TO_RESUME_STEP[_REASON_SUBMITTER_NOT_FOUND] == "2C"
    assert REASON_TO_RESUME_STEP[_REASON_SUBMITTER_INACTIVE] == "2C"
    assert REASON_TO_RESUME_STEP[_REASON_POLICY] == "2D"
    assert REASON_TO_RESUME_STEP[_REASON_RECEIPT] == "2E"
    assert REASON_TO_RESUME_STEP[_REASON_CURRENCY] == "2F"
    assert REASON_TO_RESUME_STEP[_REASON_COA] == "2G"


def test_resume_step_reached() -> None:
    assert _resume_step_reached("2C", "2A") is False
    assert _resume_step_reached("2C", "2C") is True
    assert _resume_step_reached("2C", "2G") is True
    assert _resume_step_reached(None, "2A") is True


def test_pop_resume_from_step() -> None:
    case = SimpleNamespace(
        workflow_metadata={"resume_from_step": "2F", "extracted_fields": {}},
    )
    step = _pop_resume_from_step(case)
    assert step == "2F"
    assert "resume_from_step" not in (case.workflow_metadata or {})
