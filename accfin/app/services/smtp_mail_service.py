"""Shared-relay SMTP send via aiosmtplib — `14` §7b, `18` §10."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

import aiosmtplib

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MailAttachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


class SmtpMailService:
    """Send MIME messages through the platform SMTP relay with per-mailbox auth."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _format_message_id(self, domain: str) -> str:
        return make_msgid(domain=domain.split("@")[-1] if "@" in domain else domain)

    def build_message(
        self,
        *,
        from_address: str,
        from_name: str | None,
        to_addresses: list[str],
        cc_addresses: list[str] | None,
        subject: str,
        body_plain: str,
        body_html: str | None = None,
        attachments: list[MailAttachment] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> tuple[MIMEMultipart, str]:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = formataddr((from_name or from_address, from_address))
        msg["To"] = ", ".join(to_addresses)
        if cc_addresses:
            msg["Cc"] = ", ".join(cc_addresses)
        wire_id = self._format_message_id(from_address)
        msg["Message-ID"] = wire_id

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = " ".join(references)

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_plain, "plain", "utf-8"))
        if body_html:
            alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)

        for attachment in attachments or []:
            maintype, _, subtype = attachment.mime_type.partition("/")
            part = MIMEBase(maintype or "application", subtype or "octet-stream")
            part.set_payload(attachment.content)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment.filename,
            )
            msg.attach(part)

        return msg, wire_id

    async def send(
        self,
        message: MIMEMultipart,
        *,
        username: str,
        password: str,
    ) -> None:
        cfg = self._settings
        recipients: list[str] = []
        for header in ("To", "Cc", "Bcc"):
            raw = message.get(header)
            if raw:
                recipients.extend(addr.strip() for addr in raw.split(",") if addr.strip())

        kwargs: dict = {
            "hostname": cfg.smtp_host,
            "port": cfg.smtp_port,
            "username": username,
            "password": password,
            "timeout": cfg.smtp_timeout_seconds,
        }
        if cfg.smtp_use_starttls:
            kwargs["start_tls"] = True
            kwargs["use_tls"] = False
        elif cfg.smtp_use_tls:
            kwargs["use_tls"] = True
        else:
            kwargs["use_tls"] = False

        await aiosmtplib.send(message, recipients=recipients, **kwargs)

    async def send_message(
        self,
        *,
        from_address: str,
        from_name: str | None,
        username: str,
        password: str,
        to_addresses: list[str],
        cc_addresses: list[str] | None = None,
        subject: str,
        body_plain: str,
        body_html: str | None = None,
        attachments: list[MailAttachment] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> str:
        message, wire_id = self.build_message(
            from_address=from_address,
            from_name=from_name,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            body_plain=body_plain,
            body_html=body_html,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
        )
        try:
            await self.send(message, username=username, password=password)
        except Exception:
            logger.exception(
                "SMTP send failed from=%s to=%s subject=%s",
                from_address,
                to_addresses,
                subject[:80],
            )
            raise
        return wire_id
