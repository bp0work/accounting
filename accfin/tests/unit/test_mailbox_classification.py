"""Tests for mailbox-first classification."""

from uuid import UUID

from agents.hermes.classify import classify_email_stub
from app.schemas.hermes import ClassifyEmailRequest


def test_accexp_mailbox_routes_expense_claim():
    resp = classify_email_stub(
        ClassifyEmailRequest(
            email_id=UUID("00000000-0000-0000-0000-000000000001"),
            subject="Random subject without invoice keyword",
            body_preview="Please reimburse",
            from_address="user@bp0.work",
            mailbox="accexp.mmlogistix@bp0.work",
            valid_case_types=["expense_claim", "general_inquiry"],
        )
    )
    assert resp.output is not None
    assert resp.output.case_type == "expense_claim"
    assert resp.confidence_score >= 0.90


def test_accexp_mailbox_invoice_subject_still_expense_claim():
    """Employee reimbursement invoices to accexp must not classify as ap_invoice."""
    resp = classify_email_stub(
        ClassifyEmailRequest(
            email_id=UUID("00000000-0000-0000-0000-000000000003"),
            subject="Invoice HO-202512-01 — Home office reimbursement",
            body_preview="Invoice No: HO-202512-01 Total: SGD 282.00",
            from_address="marc@bp0.work",
            mailbox="accexp.mmlogistix@bp0.work",
            valid_case_types=["expense_claim", "ap_invoice", "general_inquiry"],
        )
    )
    assert resp.output is not None
    assert resp.output.case_type == "expense_claim"


def test_accap_mailbox_overrides_non_invoice_subject():
    resp = classify_email_stub(
        ClassifyEmailRequest(
            email_id=UUID("00000000-0000-0000-0000-000000000002"),
            subject="Payment advice for May",
            body_preview="TT remittance",
            from_address="treasury@customer.com",
            mailbox="accap.mmlogistix@bp0.work",
            valid_case_types=["ap_invoice", "ar_payment_advice", "general_inquiry"],
        )
    )
    assert resp.output is not None
    assert resp.output.case_type == "ap_invoice"
