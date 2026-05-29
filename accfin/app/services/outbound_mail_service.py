"""Dispatch approved pending outbound rows and manager escalation mail — `17` §10.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.crypto import decrypt_field
from app.core.database import get_session_factory
from app.models.case import Case
from app.models.executive_mail import CaseEscalation, PendingOutboundEmail
from app.models.mail import Email, EmailAttachment, MailGatewayConfig
from app.models.tenant_profile import TenantProfile
from app.services import mail_template_renderer as templates
from app.services.ap_escalation_mail_labels import ap_escalation_approve_button_label
from app.services.mail_template_renderer import TenantEmailSignature
from app.services.smtp_mail_service import MailAttachment, SmtpMailService

logger = logging.getLogger(__name__)

TENANT_MMLOGISTIX = UUID("00000000-0000-0000-0000-000000000200")

PREFERRED_DAILY_LOG_SENDERS = (
    "acc.mmlogistix@bp0.work",
    "system.mmlogistix@bp0.work",
)

MANAGER_ESCALATION_TEMPLATES = frozenset(
    {
        "manager.escalation.request",
        "manager.escalation.missing_fields",
        "manager.escalation.vendor_not_found",
    }
)


@dataclass(frozen=True)
class AckSourceData:
    """Plain email fields for ack templates — no ORM after external awaits."""

    message_id: str
    from_name: str | None
    subject: str
    body_plain: str
    attachment_filenames: list[str]
    received_at_display: str


@dataclass(frozen=True)
class OutboundSendPlan:
    """SMTP payload built entirely inside an async DB session."""

    outbound_id: UUID
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    body_plain: str
    body_html: str | None
    attachments: list[MailAttachment]
    in_reply_to: str | None
    references: list[str] | None
    from_address: str
    from_name: str | None
    username: str
    password: str
    metadata: dict


class OutboundMailService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._smtp = SmtpMailService(self._settings)

    def _smtp_ready(self) -> bool:
        return self._settings.smtp_configured

    async def _load_tenant_signature(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID | None = None,
    ) -> TenantEmailSignature:
        tid = tenant_id or TENANT_MMLOGISTIX
        profile = await session.get(TenantProfile, tid)
        if profile is None:
            return TenantEmailSignature()
        return TenantEmailSignature(
            html=(profile.email_signature_html or "").strip(),
            plain=(profile.email_signature_plain or "").strip(),
        )

    @staticmethod
    def _normalize_msg_id(message_id: str | None) -> str | None:
        if not message_id:
            return None
        mid = message_id.strip()
        if not mid.startswith("<"):
            mid = f"<{mid}>"
        return mid

    async def _load_mailbox(self, session: AsyncSession, mailbox_id: UUID) -> MailGatewayConfig | None:
        result = await session.execute(
            select(MailGatewayConfig).where(MailGatewayConfig.id == mailbox_id)
        )
        return result.scalar_one_or_none()

    async def _load_ack_source_data(
        self, session: AsyncSession, email_id: UUID
    ) -> AckSourceData | None:
        result = await session.execute(
            select(Email)
            .options(selectinload(Email.attachments))
            .where(Email.id == email_id)
        )
        email = result.scalar_one_or_none()
        if email is None:
            return None

        body = (email.body_text or email.body_preview or "").strip()
        if len(body) > 2000:
            body = body[:2000] + "\n…"

        return AckSourceData(
            message_id=email.message_id,
            from_name=email.from_name,
            subject=email.subject,
            body_plain=body,
            attachment_filenames=[att.filename for att in email.attachments],
            received_at_display=email.received_at.isoformat() if email.received_at else "",
        )

    async def _load_reattach_attachments(
        self,
        session: AsyncSession,
        email_id: UUID,
        *,
        reattach: bool,
    ) -> list[MailAttachment]:
        if not reattach:
            return []

        result = await session.execute(
            select(EmailAttachment).where(EmailAttachment.email_id == email_id)
        )
        base = Path(self._settings.attachment_storage_path)
        attachments: list[MailAttachment] = []
        for att in result.scalars().all():
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

    def _ack_template_context(self, ack: AckSourceData, case_number: str) -> dict:
        return {
            "case_number": case_number,
            "sender_name": ack.from_name,
            "original_subject": ack.subject,
            "attachment_filenames": ack.attachment_filenames,
            "received_at_display": ack.received_at_display,
            "original_body_plain": ack.body_plain,
        }

    async def _build_send_plan(
        self,
        session: AsyncSession,
        outbound: PendingOutboundEmail,
    ) -> OutboundSendPlan | None:
        if outbound.status != "approved":
            return None

        signature = await self._load_tenant_signature(session)
        mailbox = await self._load_mailbox(session, outbound.mailbox_id)
        if mailbox is None:
            logger.warning("Outbound %s: mailbox %s not found", outbound.id, outbound.mailbox_id)
            return None

        meta = dict(outbound.metadata_ or {})
        template_key = meta.get("template")
        body_plain = outbound.body_plain
        body_html = outbound.body_html
        in_reply_to: str | None = None
        references: list[str] | None = None
        reattach = bool(meta.get("reattach_inbound_attachments"))
        attachments: list[MailAttachment] = []
        signed_via_template = False

        if template_key in MANAGER_ESCALATION_TEMPLATES:
            reason_code = meta.get("reason_code")
            render_ctx = {
                "case_number": str(meta.get("case_number", "")),
                "summary": meta.get("summary", body_plain),
                "error_reason": meta.get("error_reason", ""),
                "executive_mailbox": meta.get("executive_mailbox", ""),
                "approve_url": meta.get("approve_url", ""),
                "reject_url": meta.get("reject_url", ""),
                "escalate_url": meta.get("escalate_url", ""),
                "request_info_url": meta.get("request_info_url", ""),
                "approve_label": meta.get("approve_label")
                or ap_escalation_approve_button_label(
                    str(reason_code) if reason_code else None
                ),
                "missing_fields": meta.get("missing_fields") or [],
                "extracted_fields": meta.get("extracted_fields") or {},
                "extraction_confidence": meta.get("extraction_confidence"),
            }
            if template_key == "manager.escalation.missing_fields":
                body_plain, body_html = templates.render_missing_fields_escalation(
                    render_ctx, signature=signature
                )
            elif template_key == "manager.escalation.vendor_not_found":
                body_plain, body_html = templates.render_vendor_not_found_escalation(
                    render_ctx, signature=signature
                )
            else:
                body_plain, body_html = templates.render_manager_escalation(
                    render_ctx, signature=signature
                )

        if outbound.email_id:
            ack_data = await self._load_ack_source_data(session, outbound.email_id)
            if ack_data is not None:
                in_reply_to = self._normalize_msg_id(ack_data.message_id)
                references = [in_reply_to] if in_reply_to else None

                if template_key == "mail.intake.acknowledged":
                    ctx = self._ack_template_context(
                        ack_data,
                        str(meta.get("case_number", "")),
                    )
                    body_plain, body_html = templates.render_acknowledgement(
                        ctx, signature=signature
                    )
                    signed_via_template = True
                    if not reattach and ctx["attachment_filenames"]:
                        meta["reattach_inbound_attachments"] = True
                        reattach = True

                if (
                    template_key in MANAGER_ESCALATION_TEMPLATES
                    and ack_data.attachment_filenames
                    and not reattach
                ):
                    meta["reattach_inbound_attachments"] = True
                    reattach = True

            attachments = await self._load_reattach_attachments(
                session,
                outbound.email_id,
                reattach=reattach,
            )

        if not signed_via_template:
            body_plain, body_html = templates.append_tenant_signature(
                body_plain,
                body_html,
                signature=signature,
            )

        return OutboundSendPlan(
            outbound_id=outbound.id,
            to_addresses=list(outbound.to_addresses),
            cc_addresses=list(outbound.cc_addresses or []),
            subject=outbound.subject,
            body_plain=body_plain,
            body_html=body_html,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
            from_address=mailbox.email_address,
            from_name=mailbox.display_name,
            username=mailbox.username,
            password=decrypt_field(mailbox.password_encrypted),
            metadata=meta,
        )

    async def _mark_pending_sent(
        self,
        session: AsyncSession,
        *,
        outbound_id: UUID,
        wire_id: str,
        metadata: dict,
    ) -> None:
        result = await session.execute(
            select(PendingOutboundEmail).where(PendingOutboundEmail.id == outbound_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.status = "sent"
        row.sent_at = datetime.now(UTC)
        row.smtp_message_id = wire_id
        metadata.pop("last_send_error", None)
        row.metadata_ = metadata
        await session.flush()

    async def _mark_pending_send_failed(
        self,
        session: AsyncSession,
        *,
        outbound_id: UUID,
        metadata: dict,
        error: str,
    ) -> None:
        result = await session.execute(
            select(PendingOutboundEmail).where(PendingOutboundEmail.id == outbound_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        metadata["last_send_error"] = error[:500]
        row.metadata_ = metadata
        await session.flush()

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

        # Same-session path (classification / executive mail during open transaction).
        plan = await self._build_send_plan(self._session, outbound)
        if plan is None:
            return None

        try:
            wire_id = await self._smtp.send_message(
                from_address=plan.from_address,
                from_name=plan.from_name,
                username=plan.username,
                password=plan.password,
                to_addresses=plan.to_addresses,
                cc_addresses=plan.cc_addresses,
                subject=plan.subject,
                body_plain=plan.body_plain,
                body_html=plan.body_html,
                attachments=plan.attachments,
                in_reply_to=plan.in_reply_to,
                references=plan.references,
            )
        except Exception as exc:
            await self._mark_pending_send_failed(
                self._session,
                outbound_id=plan.outbound_id,
                metadata=plan.metadata,
                error=str(exc),
            )
            return None

        await self._mark_pending_sent(
            self._session,
            outbound_id=plan.outbound_id,
            wire_id=wire_id,
            metadata=plan.metadata,
        )
        outbound.status = "sent"
        outbound.sent_at = datetime.now(UTC)
        outbound.smtp_message_id = wire_id
        outbound.metadata_ = plan.metadata
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
        request_info_url = notification.get("request_info_url", "")
        error_reason = (escalation.context or {}).get("error_reason", "")
        template_key = notification.get("template", "manager.escalation.request")

        ctx = {
            "case_number": case.case_number,
            "summary": escalation.summary,
            "error_reason": error_reason,
            "executive_mailbox": executive_mailbox.email_address,
            "approve_url": approve_url,
            "reject_url": reject_url,
            "escalate_url": escalate_url,
            "request_info_url": request_info_url,
            "approve_label": ap_escalation_approve_button_label(escalation.reason_code),
            "missing_fields": (escalation.context or {}).get("missing_fields") or [],
            "extracted_fields": (escalation.context or {}).get("extracted_fields") or {},
            "extraction_confidence": (escalation.context or {}).get("extraction_confidence"),
            "manager_comment": (escalation.context or {}).get("manager_comment"),
            "forwarded_from": (escalation.context or {}).get("forwarded_from"),
        }
        signature = await self._load_tenant_signature(self._session)
        if template_key == "manager.escalation.missing_fields":
            body_plain, body_html = templates.render_missing_fields_escalation(
                ctx, signature=signature
            )
            subject = f"[{case.case_number}] Action required — missing invoice fields"
        elif template_key == "manager.escalation.vendor_not_found":
            body_plain, body_html = templates.render_vendor_not_found_escalation(
                ctx, signature=signature
            )
            subject = f"[{case.case_number}] Action required — vendor not set up"
        else:
            body_plain, body_html = templates.render_manager_escalation(ctx, signature=signature)
            subject = f"[{case.case_number}] Action required — manager review"

        try:
            password = decrypt_field(executive_mailbox.password_encrypted)
            email_id = escalation.email_id or case.email_id
            attachments: list[MailAttachment] = []
            if email_id:
                attachments = await self._load_reattach_attachments(
                    self._session,
                    email_id,
                    reattach=bool(
                        (escalation.context or {})
                        .get("notification", {})
                        .get("reattach_inbound_attachments")
                    ),
                )
            wire_id = await self._smtp.send_message(
                from_address=executive_mailbox.email_address,
                from_name=executive_mailbox.display_name,
                username=executive_mailbox.username,
                password=password,
                to_addresses=[escalation.target_email],
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
                attachments=attachments,
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

        signature = await self._load_tenant_signature(self._session)
        ctx = {
            "business_date": business_date.isoformat(),
            "row_count": row_count,
            "mailbox_summary": mailbox_summary or [],
            "attachment_filename": filename,
        }
        body_plain, body_html = templates.render_daily_log(ctx, signature=signature)
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

    async def send_notification(
        self,
        *,
        mailbox: MailGatewayConfig,
        to_addresses: list[str],
        subject: str,
        body_plain: str,
        body_html: str | None = None,
        tenant_id: UUID | None = None,
        attachments: list[MailAttachment] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> str | None:
        """Send a one-off SMTP notification with tenant signature appended."""
        if not self._smtp_ready():
            return None

        signature = await self._load_tenant_signature(self._session, tenant_id=tenant_id)
        signed_plain, signed_html = templates.append_tenant_signature(
            body_plain,
            body_html,
            signature=signature,
        )
        try:
            password = decrypt_field(mailbox.password_encrypted)
            return await self._smtp.send_message(
                from_address=mailbox.email_address,
                from_name=mailbox.display_name,
                username=mailbox.username,
                password=password,
                to_addresses=to_addresses,
                subject=subject,
                body_plain=signed_plain,
                body_html=signed_html,
                attachments=attachments or [],
                in_reply_to=in_reply_to,
                references=references,
            )
        except Exception:
            logger.exception("Notification SMTP send failed to %s", to_addresses)
            return None

    async def send_gl_cutoff_reminder(
        self,
        *,
        mailbox: MailGatewayConfig,
        to_address: str,
        days_until: int,
        period_name: str,
        period_type: str,
        cutoff: date,
        status: str,
        reviewer: str,
        tenant_id: UUID | None = None,
    ) -> str | None:
        """Send GL cutoff reminder email with tenant signature."""
        if not self._smtp_ready():
            return None

        if days_until == 0:
            subject = f"[Reminder] GL cutoff today — {period_name}"
            lead = f"The GL posting cutoff for {period_name} is today ({cutoff.isoformat()})."
        else:
            subject = f"[Reminder] GL cutoff in {days_until} days — {period_name}"
            lead = (
                f"The GL posting cutoff for {period_name} is in {days_until} days "
                f"({cutoff.isoformat()})."
            )

        signature = await self._load_tenant_signature(self._session, tenant_id=tenant_id)
        body_plain, body_html = templates.render_gl_cutoff_reminder(
            {
                "lead": lead,
                "period_type": period_type,
                "cutoff_date": cutoff.isoformat(),
                "status": status,
                "reviewer": reviewer,
                "calendar_url": "https://admin.mmlogistix.bp0.work/accounting-calendar",
            },
            signature=signature,
        )

        try:
            password = decrypt_field(mailbox.password_encrypted)
            return await self._smtp.send_message(
                from_address=mailbox.email_address,
                from_name=mailbox.display_name or "mmlogistix Accounts",
                username=mailbox.username,
                password=password,
                to_addresses=[to_address],
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
            )
        except Exception:
            logger.exception(
                "GL cutoff reminder SMTP failed period=%s recipient=%s",
                period_name,
                to_address,
            )
            return None

    async def flush_approved(self, *, limit: int = 25) -> int:
        """Send approved pending rows — each via phased session_factory (cron catch-up)."""
        if not self._smtp_ready():
            return 0

        result = await self._session.execute(
            select(PendingOutboundEmail.id)
            .where(PendingOutboundEmail.status == "approved")
            .order_by(PendingOutboundEmail.created_at.asc())
            .limit(limit)
        )
        outbound_ids = [row[0] for row in result.all()]
        sent = 0
        for outbound_id in outbound_ids:
            if await send_pending_outbound_email(outbound_id):
                sent += 1
        return sent


async def send_pending_outbound_email(outbound_id: UUID) -> str | None:
    """
    Production catch-up path: load → SMTP → persist in separate session scopes.
    Mirrors `gateway/imap/poller.py` / accounts classification phased DB pattern.
    """
    if not get_settings().smtp_configured:
        return None

    factory = get_session_factory()
    smtp = SmtpMailService()

    async with factory() as session:
        svc = OutboundMailService(session)
        result = await session.execute(
            select(PendingOutboundEmail).where(PendingOutboundEmail.id == outbound_id)
        )
        outbound = result.scalar_one_or_none()
        if outbound is None or outbound.status != "approved":
            return None
        plan = await svc._build_send_plan(session, outbound)
        if plan is None:
            return None

    try:
        wire_id = await smtp.send_message(
            from_address=plan.from_address,
            from_name=plan.from_name,
            username=plan.username,
            password=plan.password,
            to_addresses=plan.to_addresses,
            cc_addresses=plan.cc_addresses,
            subject=plan.subject,
            body_plain=plan.body_plain,
            body_html=plan.body_html,
            attachments=plan.attachments,
            in_reply_to=plan.in_reply_to,
            references=plan.references,
        )
    except Exception as exc:
        async with factory() as session:
            svc = OutboundMailService(session)
            await svc._mark_pending_send_failed(
                session,
                outbound_id=plan.outbound_id,
                metadata=plan.metadata,
                error=str(exc),
            )
            await session.commit()
        return None

    async with factory() as session:
        svc = OutboundMailService(session)
        await svc._mark_pending_sent(
            session,
            outbound_id=plan.outbound_id,
            wire_id=wire_id,
            metadata=plan.metadata,
        )
        await session.commit()

    return wire_id
