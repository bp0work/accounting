"""Classification routing matrix — `17` §3.1, `12`."""

from uuid import UUID

from agents.hermes.classify import classify_email_stub
from app.schemas.hermes import ClassifyEmailRequest
from workers.accounts.classification import routing_decision


def test_routing_high_confidence_stp():
    status, priority, stp, trigger = routing_decision(
        case_type="ap_invoice", confidence=0.95, stp_from_hermes=True
    )
    assert status == "classified"
    assert priority == "high"
    assert stp is True
    assert trigger == "ai_classified"


def test_routing_low_confidence_manual():
    status, priority, stp, trigger = routing_decision(
        case_type="ap_invoice", confidence=0.55, stp_from_hermes=False
    )
    assert status == "manual_review"
    assert trigger == "classification_failed"


def test_hermes_stub_invoice_subject():
    resp = classify_email_stub(
        ClassifyEmailRequest(
            email_id=UUID("00000000-0000-0000-0000-000000000001"),
            subject="Invoice INV-100",
            body_preview="Please pay",
            from_address="a@b.com",
            mailbox="accap.mmlogistix@bp0.work",
            valid_case_types=["ap_invoice", "general_inquiry"],
        )
    )
    assert resp.output is not None
    assert resp.output.case_type == "ap_invoice"
    assert resp.confidence_score >= 0.70
