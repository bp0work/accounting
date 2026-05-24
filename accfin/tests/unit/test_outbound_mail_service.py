"""Unit tests for SMTP outbound mail."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mail_template_renderer import render_acknowledgement, render_manager_escalation
from app.services.smtp_mail_service import MailAttachment, SmtpMailService


def test_render_acknowledgement_includes_case_number():
    plain, html = render_acknowledgement(
        {
            "case_number": "CAS-20260524-0001",
            "sender_name": "Vendor Co",
            "original_subject": "Invoice 123",
        }
    )
    assert "CAS-20260524-0001" in plain
    assert "CAS-20260524-0001" in html
    assert "Invoice 123" in plain


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
        }
    )
    assert "https://example.test/approve" in plain
    assert "https://example.test/approve" in html


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
async def test_try_send_pending_marks_row_sent():
    from app.models.executive_mail import PendingOutboundEmail
    from app.services.outbound_mail_service import OutboundMailService

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
        metadata_={"template": "mail.intake.acknowledged", "case_number": "CAS-1"},
    )
    mailbox = MagicMock()
    mailbox.id = outbound.mailbox_id
    mailbox.email_address = "accap.mmlogistix@bp0.work"
    mailbox.display_name = "AP"
    mailbox.username = "accap.mmlogistix@bp0.work"
    mailbox.password_encrypted = "enc"

    session = AsyncMock()

    async def execute_side_effect(_stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mailbox
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.flush = AsyncMock()

    svc = OutboundMailService(session)
    svc._smtp_ready = MagicMock(return_value=True)  # type: ignore[method-assign]

    with patch.object(svc, "_load_source_email", new=AsyncMock(return_value=None)):
        with patch(
            "app.services.outbound_mail_service.decrypt_field",
            return_value="pw",
        ):
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
