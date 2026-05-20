"""State machine transition and guard tests — `08` §12, `12`."""

from types import SimpleNamespace

from app.core.state_machine import CaseStateMachine, CaseStatus


def _case(status: str, **kwargs):
    defaults = {
        "status": status,
        "confidence_score": 0.95,
        "risk_flags": [],
        "amount_value": 1000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_ai_classified_high_confidence():
    machine = CaseStateMachine()
    case = _case(CaseStatus.INBOUND.value)
    result = machine.transition(case, "ai_classified", context={"confidence": 0.85})
    assert result.success
    assert case.status == CaseStatus.CLASSIFIED.value


def test_classification_failed_low_confidence():
    machine = CaseStateMachine()
    case = _case(CaseStatus.INBOUND.value)
    result = machine.transition(case, "classification_failed", context={"confidence": 0.50})
    assert result.success
    assert case.status == CaseStatus.MANUAL_REVIEW.value


def test_human_classified_requires_permission():
    machine = CaseStateMachine()
    case = _case(CaseStatus.INBOUND.value)
    actor = SimpleNamespace(permissions=["cases:read"])
    result = machine.transition(case, "human_classified", actor=actor)
    assert not result.success

    actor.permissions = ["cases:write"]
    result = machine.transition(case, "human_classified", actor=actor)
    assert result.success


def test_processing_error_retry_vs_manual():
    machine = CaseStateMachine()
    workflow_low = SimpleNamespace(retry_count=0, max_retries=3)
    workflow_max = SimpleNamespace(retry_count=3, max_retries=3)

    case_retry = _case(CaseStatus.PROCESSING.value)
    r1 = machine.transition(
        case_retry, "processing_error", context={"workflow": workflow_low}
    )
    assert r1.success
    assert case_retry.status == CaseStatus.EXCEPTION.value

    case_manual = _case(CaseStatus.PROCESSING.value)
    r2 = machine.transition(
        case_manual, "processing_error", context={"workflow": workflow_max}
    )
    assert r2.success
    assert case_manual.status == CaseStatus.MANUAL_REVIEW.value
