"""Unit tests — escalation respond HTML pages."""

from uuid import UUID

from app.services.mail_escalation_pages import (
    action_label,
    html_escalation_confirmation,
    html_escalation_form,
)


def test_action_label():
    assert action_label("approve") == "Approved"
    assert action_label("reject") == "Rejected"


def test_html_escalation_form_includes_case_and_action():
    html = html_escalation_form(
        escalation_id=UUID("00000000-0000-0000-0000-000000000001"),
        case_number="CAS-TEST-001",
        action="approve",
        token="test-token",
    )
    assert "CAS-TEST-001" in html
    assert "Approved" in html
    assert 'name="comment"' in html
    assert "method=\"post\"" in html


def test_html_escalation_confirmation_shows_comment():
    html = html_escalation_confirmation(
        case_number="CAS-TEST-002",
        action="approve",
        comment="Approved — recurring ACRA fee",
    )
    assert "CAS-TEST-002" in html
    assert "Approved — recurring ACRA fee" in html
