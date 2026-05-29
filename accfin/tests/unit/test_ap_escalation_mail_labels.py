"""Unit tests for AP manager escalation email approve button labels."""

from __future__ import annotations

import pytest

from app.services.ap_escalation_mail_labels import ap_escalation_approve_button_label
from app.services.mail_template_renderer import render_manager_escalation


@pytest.mark.parametrize(
    ("reason_code", "expected"),
    [
        ("AP_CONTRACT_MISSING", "Resubmit"),
        ("AP_VENDOR_INACTIVE", "Reactivate & Resubmit"),
        ("AP_PAYMENT_TERMS_MISMATCH", "Accept & Continue"),
        ("AP_SENDER_NOT_VALIDATED", "Accept & Continue"),
        ("AP_COA_NOT_FOUND", "Confirm Account & Continue"),
        ("AP_CURRENCY_CONVERSION_REQUIRED", "Apply Rate & Continue"),
        ("AP_DUPLICATE_FOUND", "Approve"),
        (None, "Approve"),
    ],
)
def test_ap_escalation_approve_button_label(reason_code: str | None, expected: str) -> None:
    assert ap_escalation_approve_button_label(reason_code) == expected


def test_render_manager_escalation_uses_custom_approve_label() -> None:
    plain, html = render_manager_escalation(
        {
            "case_number": "CAS-1",
            "summary": "Contract not on file",
            "approve_url": "https://example.test/approve",
            "reject_url": "https://example.test/reject",
            "escalate_url": "https://example.test/escalate",
            "approve_label": "Resubmit",
        }
    )
    assert "Resubmit:" in plain
    assert "Resubmit" in html
    assert "Approve:" not in plain
    assert ">Approve</a>" not in html
    assert "Reject:" in plain
