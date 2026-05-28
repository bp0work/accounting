"""Unit tests — AP_VENDOR_NOT_FOUND reject-only escalation."""

import pytest

from app.services.mail_template_renderer import render_vendor_not_found_escalation


def test_vendor_not_found_escalation_reject_only():
    plain, html = render_vendor_not_found_escalation(
        {
            "case_number": "CAS-20260528-0002",
            "summary": "Vendor ACME has no subaccount.",
            "error_reason": "AP_VENDOR_NOT_FOUND",
            "executive_mailbox": "accap.mmlogistix@bp0.work",
            "reject_url": "https://example.test/reject",
        }
    )
    assert "https://example.test/reject" in plain
    assert "https://example.test/reject" in html
    assert "Approve:" not in plain
    assert "Escalate:" not in plain
    assert "Retry button" in plain
    assert "Finance UI" in plain
    assert "Reject" in html
    assert "approve_url" not in html


@pytest.mark.asyncio
async def test_escalation_approve_blocked_for_vendor_not_found():
    from unittest.mock import AsyncMock, MagicMock
    from uuid import uuid4

    from app.services.escalation_service import EscalationService

    escalation_id = uuid4()
    case_id = uuid4()
    row = MagicMock()
    row.id = escalation_id
    row.case_id = case_id
    row.status = "pending"
    row.reason_code = "AP_VENDOR_NOT_FOUND"
    row.response_token_hash = "hash"
    row.target_email = "acc.mmlogistix@bp0.work"
    row.context = {}
    row.summary = "Vendor missing"

    service = EscalationService(AsyncMock())
    service._validate_token = MagicMock(return_value="hash")
    service._repo.get = AsyncMock(return_value=row)

    from app.core.exceptions import AppHTTPException

    with pytest.raises(AppHTTPException) as exc_info:
        await service.respond(
            escalation_id,
            action="approve",
            wire_token="wire",
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "VENDOR_NOT_FOUND_NO_APPROVE"
