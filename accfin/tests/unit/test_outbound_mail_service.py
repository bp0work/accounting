"""Unit tests for SMTP outbound mail."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mail_template_renderer import (
    render_acknowledgement,
    render_manager_escalation,
    render_missing_fields_escalation,
)
from app.services.smtp_mail_service import MailAttachment, SmtpMailService


def test_render_acknowledgement_includes_case_number():
    plain, html = render_acknowledgement(
        {
            "case_number": "CAS-20260524-0001",
            "sender_name": "Vendor Co",
            "original_subject": "Invoice 123",
            "attachment_filenames": ["invoice.pdf"],
            "received_at_display": "2026-05-24T08:00:00+00:00",
            "original_body_plain": "Please process this invoice.",
        }
    )
    assert "CAS-20260524-0001" in plain
    assert "CAS-20260524-0001" in html
    assert "Invoice 123" in plain
    assert "invoice.pdf" in plain


def test_render_missing_fields_escalation_includes_request_info():
    plain, html = render_missing_fields_escalation(
        {
            "case_number": "CAS-20260524-0002",
            "summary": "Missing invoice fields",
            "extraction_confidence": 0.55,
            "extracted_fields": {"vendor_name": "Acme", "document_number": None},
            "missing_fields": ["document_number", "document_date"],
            "executive_mailbox": "accap.mmlogistix@bp0.work",
            "approve_url": "https://example.test/approve",
            "request_info_url": "https://example.test/request-info",
            "reject_url": "https://example.test/reject",
        }
    )
    assert "document_number" in plain
    assert "document_date" in plain
    assert "Request more info" in plain
    assert "Request More Info" in html
    assert "https://example.test/request-info" in html


def test_render_vendor_not_found_escalation_reject_only():
    from app.services.mail_template_renderer import render_vendor_not_found_escalation

    plain, html = render_vendor_not_found_escalation(
        {
            "case_number": "CAS-1",
            "summary": "No subaccount",
            "reject_url": "https://example.test/reject",
        }
    )
    assert "https://example.test/reject" in plain
    assert "Approve:" not in plain
    assert "Retry button" in plain


def test_render_manager_escalation_includes_action_urls():
    plain, html = render_manager_escalation(
        {
            "case_number": "CAS-20260524-0001",
            "summary": "Hermes timeout",
            "error_reason": "HERMES_TIMEOUT",
            "executive_mailbox": "accap.mmlogistix@bp0.work",
            "approve_url": "https://example.test/approve",
            "reject_url": "https://example.test/reject",
            "escalate_url": "https://example.test/escalate",
            "approve_label": "Approve",
        }
    )
    assert "https://example.test/approve" in plain
    assert "https://example.test/approve" in html
    assert "Approve:" in plain


def test_build_message_sets_thread_headers():
    svc = SmtpMailService()
    msg, wire_id = svc.build_message(
        from_address="accap.mmlogistix@bp0.work",
        from_name="Accounts Payable",
        to_addresses=["vendor@example.com"],
        cc_addresses=None,
        subject="Re: test",
        body_plain="Hello",
        in_reply_to="<original@example.com>",
        references=["<original@example.com>"],
    )
    assert msg["In-Reply-To"] == "<original@example.com>"
    assert "<original@example.com>" in msg["References"]
    assert wire_id.startswith("<")


@pytest.mark.asyncio
async def test_send_message_calls_aiosmtplib(monkeypatch):
    sent = []

    async def fake_send(message, **kwargs):
        sent.append(message)
        assert kwargs["hostname"] == "mail.test"
        assert kwargs["port"] == 465
        assert kwargs["username"] == "accap.mmlogistix@bp0.work"

    monkeypatch.setenv("FINANCE_SMTP__ENABLED", "true")
    monkeypatch.setenv("FINANCE_SMTP__HOST", "mail.test")
    monkeypatch.setenv("FINANCE_SMTP__PORT", "465")
    from app.core.config import get_settings

    get_settings.cache_clear()

    with patch("app.services.smtp_mail_service.aiosmtplib.send", new=AsyncMock(side_effect=fake_send)):
        svc = SmtpMailService()
        wire_id = await svc.send_message(
            from_address="accap.mmlogistix@bp0.work",
            from_name="AP",
            username="accap.mmlogistix@bp0.work",
            password="secret",
            to_addresses=["vendor@example.com"],
            subject="Test",
            body_plain="Body",
            attachments=[
                MailAttachment(filename="log.csv", content=b"a,b", mime_type="text/csv"),
            ],
        )

    assert wire_id.startswith("<")
    assert len(sent) == 1
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_build_send_plan_manager_escalation_reattaches(tmp_path, monkeypatch):
    from app.models.executive_mail import PendingOutboundEmail
    from app.services.outbound_mail_service import OutboundMailService

    email_id = uuid.uuid4()
    att_dir = tmp_path / str(email_id)
    att_dir.mkdir()
    pdf_path = att_dir / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-test")

    outbound = PendingOutboundEmail(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        email_id=email_id,
        mailbox_id=uuid.uuid4(),
        to_addresses=["acc.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject="[CAS-1] Action required — missing invoice fields",
        body_plain="Summary",
        message_type="other",
        status="approved",
        metadata_={
            "template": "manager.escalation.missing_fields",
            "case_number": "CAS-1",
            "reattach_inbound_attachments": True,
            "summary": "Missing document_number",
            "error_reason": "Missing document_number",
            "approve_url": "https://example.test/approve",
            "request_info_url": "https://example.test/info",
            "reject_url": "https://example.test/reject",
            "missing_fields": ["document_number"],
            "extracted_fields": {"vendor_name": "Acme"},
            "extraction_confidence": 0.55,
        },
    )

    mailbox = MagicMock()
    mailbox.id = outbound.mailbox_id
    mailbox.email_address = "accap.mmlogistix@bp0.work"
    mailbox.display_name = "AP"
    mailbox.username = "accap.mmlogistix@bp0.work"
    mailbox.password_encrypted = "enc"

    from app.models.mail import Email, EmailAttachment

    source_email = Email(
        id=email_id,
        message_id="<orig@test>",
        mailbox_address="accap.mmlogistix@bp0.work",
        from_address="vendor@example.com",
        to_addresses=["accap.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject="Invoice",
        body_preview="Please pay",
        status="classified",
    )
    attachment = EmailAttachment(
        id=uuid.uuid4(),
        email_id=email_id,
        filename="invoice.pdf",
        storage_path=f"{email_id}/invoice.pdf",
        mime_type="application/pdf",
        size_bytes=8,
    )
    source_email.attachments = [attachment]

    session = AsyncMock()

    async def execute_side_effect(stmt):
        result = MagicMock()
        stmt_str = str(stmt)
        if "mail_gateway_config" in stmt_str:
            result.scalar_one_or_none.return_value = mailbox
        elif "emails" in stmt_str:
            result.scalar_one_or_none.return_value = source_email
        else:
            result.scalars.return_value.all.return_value = [attachment]
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)

    monkeypatch.setenv("FINANCE_MAIL__ATTACHMENT_STORAGE_PATH", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    svc = OutboundMailService(session)
    plan = await svc._build_send_plan(session, outbound)

    get_settings.cache_clear()
    assert plan is not None
    assert len(plan.attachments) == 1
    assert plan.attachments[0].filename == "invoice.pdf"
    assert "document_number" in plan.body_plain
    assert plan.in_reply_to == "<orig@test>"


@pytest.mark.asyncio
async def test_try_send_pending_marks_row_sent():
    from app.models.executive_mail import PendingOutboundEmail
    from app.services.outbound_mail_service import OutboundMailService, OutboundSendPlan

    outbound = PendingOutboundEmail(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        email_id=uuid.uuid4(),
        mailbox_id=uuid.uuid4(),
        to_addresses=["vendor@example.com"],
        cc_addresses=[],
        subject="[CAS-1] We received your email",
        body_plain="Thanks",
        message_type="acknowledgement",
        status="approved",
        metadata_={
            "template": "mail.intake.acknowledged",
            "case_number": "CAS-1",
            "reattach_inbound_attachments": True,
        },
    )
    plan = OutboundSendPlan(
        outbound_id=outbound.id,
        to_addresses=["vendor@example.com"],
        cc_addresses=[],
        subject=outbound.subject,
        body_plain="Thanks — rendered",
        body_html="<p>Thanks</p>",
        attachments=[],
        in_reply_to="<orig@test>",
        references=["<orig@test>"],
        from_address="accap.mmlogistix@bp0.work",
        from_name="AP",
        username="accap.mmlogistix@bp0.work",
        password="pw",
        metadata=dict(outbound.metadata_ or {}),
    )

    session = AsyncMock()
    session.flush = AsyncMock()

    svc = OutboundMailService(session)
    svc._smtp_ready = MagicMock(return_value=True)  # type: ignore[method-assign]

    with patch.object(svc, "_build_send_plan", new=AsyncMock(return_value=plan)):
        with patch.object(
            svc._smtp,
            "send_message",
            new=AsyncMock(return_value="<msg@test>"),
        ):
            wire_id = await svc.try_send_pending(outbound)

    assert wire_id == "<msg@test>"
    assert outbound.status == "sent"
    assert outbound.smtp_message_id == "<msg@test>"
    assert outbound.sent_at is not None
