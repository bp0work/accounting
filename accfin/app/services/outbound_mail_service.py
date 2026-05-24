"""Dispatch approved pending outbound rows and manager escalation mail — `17` §10.3."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.crypto import decrypt_field
from app.models.case import Case
from app.models.executive_mail import CaseEscalation, PendingOutboundEmail
from app.models.mail import Email, MailGatewayConfig
from app.services import mail_template_renderer as templates
from app.services.smtp_mail_service import MailAttachment, SmtpMailService

logger = logging.getLogger(__name__)

PREFERRED_DAILY_LOG_SENDERS = (
    "acc.mmlogistix@bp0.work",
    "system.mmlogistix@bp0.work",
)


class OutboundMailService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._smtp = SmtpMailService(self._settings)

    def _smtp_ready(self) -> bool:
        return self._settings.smtp_configured

    @staticmethod
    def _normalize_msg_id(message_id: str | None) -> str | None:
        if not message_id:
            return None
        mid = message_id.strip()
        if not mid.startswith("<"):
            mid = f"<{mid}>"
        return mid

    async def _load_mailbox(self, mailbox_id: UUID) -> MailGatewayConfig | None:
        result = await self._session.execute(
            select(MailGatewayConfig).where(MailGatewayConfig.id == mailbox_id)
        )
        return result.scalar_one_or_none()

    async def _load_source_email(self, email_id: UUID | None) -> Email | None:
        if email_id is None:
            return None
        result = await self._session.execute(
            select(Email)
            .options(selectinload(Email.attachments))
            .where(Email.id == email_id)
        )
        return result.scalar_one_or_none()

    async def _resolve_daily_log_mailbox(self) -> MailGatewayConfig | None:
        preferred = self._settings.daily_log_sender_mailbox.strip().lower()
        candidates = [preferred, *PREFERRED_DAILY_LOG_SENDERS]
        seen: set[str] = set()
        for email in candidates:
            key = email.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result = await self._session.execute(
                select(MailGatewayConfig).where(
                    MailGatewayConfig.email_address == email,
                    MailGatewayConfig.is_active.is_(True),
                )
            )
            mailbox = result.scalar_one_or_none()
            if mailbox is not None:
                return mailbox

        result = await self._session.execute(
            select(MailGatewayConfig)
            .where(MailGatewayConfig.is_active.is_(True))
            .order_by(MailGatewayConfig.email_address.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _inbound_attachments(self, email: Email | None, *, reattach: bool) -> list[MailAttachment]:
        if not reattach or email is None:
            return []
        base = Path(self._settings.attachment_storage_path)
        attachments: list[MailAttachment] = []
        for att in email.attachments:
            path = base / att.storage_path
            if not path.is_file():
                logger.warning("Attachment missing for outbound reattach: %s", path)
                continue
            attachments.append(
                MailAttachment(
                    filename=att.filename,
                    content=path.read_bytes(),
                    mime_type=att.mime_type,
                )
            )
        return attachments

    @staticmethod
    def _quote_original_body(email: Email, *, max_chars: int = 2000) -> str:
        body = (email.body_text or email.body_preview or "").strip()
        if len(body) > max_chars:
            return body[:max_chars] + "\n…"
        return body

    def _ack_template_context(self, source_email: Email, case_number: str) -> dict:
        filenames = [att.filename for att in (source_email.attachments or [])]
        received = source_email.received_at.isoformat() if source_email.received_at else ""
        return {
            "case_number": case_number,
            "sender_name": source_email.from_name,
            "original_subject": source_email.subject,
            "attachment_filenames": filenames,
            "received_at_display": received,
            "original_body_plain": self._quote_original_body(source_email),
        }

    async def try_send_pending(
        self,
        outbound: PendingOutboundEmail | None,
        *,
        source_email: Email | None = None,
    ) -> str | None:
        if outbound is None or outbound.status != "approved":
            return None
        if not self._smtp_ready():
            logger.debug("SMTP not configured; leaving outbound %s queued", outbound.id)
            return None

        mailbox = await self._load_mailbox(outbound.mailbox_id)
        if mailbox is None:
            logger.warning("Outbound %s: mailbox %s not found", outbound.id, outbound.mailbox_id)
            return None

        if source_email is None and outbound.email_id:
            source_email = await self._load_source_email(outbound.email_id)

        meta = dict(outbound.metadata_ or {})
        template_key = meta.get("template")
        body_plain = outbound.body_plain
        body_html = outbound.body_html

        if template_key == "mail.intake.acknowledged" and source_email is not None:
            ctx = self._ack_template_context(
                source_email,
                str(meta.get("case_number", "")),
            )
            body_plain, body_html = templates.render_acknowledgement(ctx)
            if not meta.get("reattach_inbound_attachments") and ctx["attachment_filenames"]:
                meta["reattach_inbound_attachments"] = True

        reattach = bool(meta.get("reattach_inbound_attachments"))
        attachments = self._inbound_attachments(source_email, reattach=reattach)

        in_reply_to = None
        references: list[str] | None = None
        if source_email is not None:
            in_reply_to = self._normalize_msg_id(source_email.message_id)
            references = [in_reply_to] if in_reply_to else None

        try:
            password = decrypt_field(mailbox.password_encrypted)
            wire_id = await self._smtp.send_message(
                from_address=mailbox.email_address,
                from_name=mailbox.display_name,
                username=mailbox.username,
                password=password,
                to_addresses=list(outbound.to_addresses),
                cc_addresses=list(outbound.cc_addresses or []),
                subject=outbound.subject,
                body_plain=body_plain,
                body_html=body_html,
                attachments=attachments,
                in_reply_to=in_reply_to,
                references=references,
            )
        except Exception as exc:
            meta["last_send_error"] = str(exc)[:500]
            outbound.metadata_ = meta
            await self._session.flush()
            return None

        outbound.status = "sent"
        outbound.sent_at = datetime.now(UTC)
        outbound.smtp_message_id = wire_id
        meta.pop("last_send_error", None)
        outbound.metadata_ = meta
        await self._session.flush()
        return wire_id

    async def try_send_manager_escalation(
        self,
        escalation: CaseEscalation | None,
        *,
        case: Case,
        executive_mailbox: MailGatewayConfig,
        source_email: Email | None = None,
    ) -> str | None:
        if escalation is None or escalation.status != "pending":
            return None
        if not self._smtp_ready():
            logger.debug("SMTP not configured; escalation %s URLs only", escalation.id)
            return None

        notification = (escalation.context or {}).get("notification") or {}
        approve_url = notification.get("approve_url", "")
        reject_url = notification.get("reject_url", "")
        escalate_url = notification.get("escalate_url", "")
        error_reason = (escalation.context or {}).get("error_reason", "")

        ctx = {
            "case_number": case.case_number,
            "summary": escalation.summary,
            "error_reason": error_reason,
            "executive_mailbox": executive_mailbox.email_address,
            "approve_url": approve_url,
            "reject_url": reject_url,
            "escalate_url": escalate_url,
        }
        body_plain, body_html = templates.render_manager_escalation(ctx)
        subject = f"[{case.case_number}] Action required — manager review"

        try:
            password = decrypt_field(executive_mailbox.password_encrypted)
            wire_id = await self._smtp.send_message(
                from_address=executive_mailbox.email_address,
                from_name=executive_mailbox.display_name,
                username=executive_mailbox.username,
                password=password,
                to_addresses=[escalation.target_email],
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
            )
        except Exception as exc:
            ctx_meta = dict(escalation.context or {})
            ctx_meta.setdefault("notification", {})["last_send_error"] = str(exc)[:500]
            escalation.context = ctx_meta
            await self._session.flush()
            return None

        ctx_meta = dict(escalation.context or {})
        notif = dict(ctx_meta.get("notification") or {})
        notif["smtp_message_id"] = wire_id
        notif.pop("last_send_error", None)
        ctx_meta["notification"] = notif
        escalation.context = ctx_meta
        await self._session.flush()
        return wire_id

    async def send_daily_log(
        self,
        *,
        business_date,
        recipient: str,
        csv_bytes: bytes,
        filename: str,
        row_count: int,
        mailbox_summary: list[dict] | None = None,
    ) -> str | None:
        if not self._smtp_ready():
            return None

        mailbox = await self._resolve_daily_log_mailbox()
        if mailbox is None:
            logger.warning("Daily log SMTP skipped — no active sending mailbox")
            return None

        ctx = {
            "business_date": business_date.isoformat(),
            "row_count": row_count,
            "mailbox_summary": mailbox_summary or [],
            "attachment_filename": filename,
        }
        body_plain, body_html = templates.render_daily_log(ctx)
        subject = f"Finance activity log — {business_date.isoformat()}"

        try:
            password = decrypt_field(mailbox.password_encrypted)
            return await self._smtp.send_message(
                from_address=mailbox.email_address,
                from_name=mailbox.display_name,
                username=mailbox.username,
                password=password,
                to_addresses=[recipient],
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
                attachments=[
                    MailAttachment(
                        filename=filename,
                        content=csv_bytes,
                        mime_type="text/csv",
                    )
                ],
            )
        except Exception:
            logger.exception("Daily log SMTP send failed to %s", recipient)
            return None

    async def flush_approved(self, *, limit: int = 25) -> int:
        """Send approved pending rows — useful for cron or startup catch-up."""
        if not self._smtp_ready():
            return 0

        result = await self._session.execute(
            select(PendingOutboundEmail)
            .where(PendingOutboundEmail.status == "approved")
            .order_by(PendingOutboundEmail.created_at.asc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        sent = 0
        for row in rows:
            wire_id = await self.try_send_pending(row)
            if wire_id:
                sent += 1
        return sent
