"""Unit tests for escalation HMAC tokens."""

import uuid

import pytest

from app.core.mail_action_token import hash_token, issue_escalation_token, verify_escalation_token


@pytest.mark.parametrize("escalation_id,case_id", [(uuid.uuid4(), uuid.uuid4())])
def test_issue_and_verify_escalation_token(escalation_id, case_id):
    wire, digest, _exp = issue_escalation_token(escalation_id=escalation_id, case_id=case_id)
    assert digest == hash_token(wire)
    payload = verify_escalation_token(wire, escalation_id=escalation_id)
    assert payload["case_id"] == str(case_id)


def test_verify_rejects_wrong_escalation_id():
    esc_id = uuid.uuid4()
    case_id = uuid.uuid4()
    wire, _, _ = issue_escalation_token(escalation_id=esc_id, case_id=case_id)
    with pytest.raises(ValueError, match="TOKEN_ESCALATION_MISMATCH"):
        verify_escalation_token(wire, escalation_id=uuid.uuid4())
