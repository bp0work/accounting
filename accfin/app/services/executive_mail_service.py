"""Executive email SOP — `01` §6.8, `17` §10.3–§10.5."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.mail_action_token import issue_escalation_token
from app.models.case import Case
from app.models.executive_mail import CaseEscalation, PendingOutboundEmail
from app.models.mail import Email, EmailAttachment, MailGatewayConfig
from app.repositories.case import CaseRepository
from app.repositories.executive_mail import CaseEscalationRepository
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.finance_activity_log_service import FinanceActivityLogService
from app.services.ap_escalation_mail_labels import ap_escalation_approve_button_label
from app.services.outbound_mail_service import OutboundMailService
from app.services.queue_router import enqueue_accounts

logger = logging.getLogger(__name__)

INTERNAL_DOMAIN = "@bp0.work"
_REASON_VENDOR_NOT_FOUND = "AP_VENDOR_NOT_FOUND"
_VENDOR_NOT_FOUND_TEMPLATE = "manager.escalation.vendor_not_found"


class ExecutiveMailService:
    """Manager-first failure flow, sender ack, and finance activity logging."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._escalations = CaseEscalationRepository(session)
        self._activity = FinanceActivityLogService(session)
        self._settings = get_settings()
        self._outbound = OutboundMailService(session)

    @staticmethod
    def is_external_sender(from_address: str) -> bool:
        addr = (from_address or "").strip().lower()
        return bool(addr) and not addr.endswith(INTERNAL_DOMAIN)

    async def log_step(
        self,
        *,
        action: str,
        summary: str,
        actor_type: str = "worker",
        actor_name: str | None = None,
        mailbox_id: UUID | None = None,
        case_id: UUID | None = None,
        email_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        await self._activity.log(
            FinanceActivityLogCreate(
                actor_type=actor_type,
                actor_name=actor_name,
                action=action,
                summary=summary,
                mailbox_id=mailbox_id,
                case_id=case_id,
                email_id=email_id,
                metadata=metadata or {},
            )
        )

    async def get_mailbox_for_address(self, email_address: str) -> MailGatewayConfig | None:
        return await self._escalations.get_mailbox_by_email(email_address)

    async def get_mailbox_by_id(self, mailbox_id: UUID) -> MailGatewayConfig | None:
        result = await self._session.execute(
            select(MailGatewayConfig).where(MailGatewayConfig.id == mailbox_id)
        )
        return result.scalar_one_or_none()

    def escalation_action_urls(
        self,
        escalation_id: UUID,
        wire_token: str,
        *,
        include_approve: bool = True,
        include_escalate: bool = True,
        include_request_info: bool = False,
    ) -> dict[str, str]:
        base = self._settings.edge_public_base_url.rstrip("/")
        qs = f"token={wire_token}"
        path = f"/api/mail/escalations/{escalation_id}/respond"
        urls: dict[str, str] = {
            "reject_url": f"{base}{path}?action=reject&{qs}",
        }
        if include_approve:
            urls["approve_url"] = f"{base}{path}?action=approve&{qs}"
        if include_request_info:
            urls["request_info_url"] = f"{base}{path}?action=request_info&{qs}"
        if include_escalate:
            urls["escalate_url"] = f"{base}{path}?action=escalate&{qs}"
        return urls

    async def _pending_escalation(self, case_id: UUID) -> CaseEscalation | None:
        result = await self._session.execute(
            select(CaseEscalation)
            .where(CaseEscalation.case_id == case_id, CaseEscalation.status == "pending")
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _inbound_attachment_count(self, email_id: UUID | None) -> int:
        if email_id is None:
            return 0
        result = await self._session.execute(
            select(func.count())
            .select_from(EmailAttachment)
            .where(EmailAttachment.email_id == email_id)
        )
        return int(result.scalar_one() or 0)

    async def _queue_manager_escalation_outbound(
        self,
        *,
        case: Case,
        escalation: CaseEscalation,
        executive: MailGatewayConfig,
        email_id: UUID | None,
        template_key: str,
        summary: str,
        error_detail: str,
        missing_fields: list[str],
        extracted_fields: dict[str, str | None],
        extraction_confidence: float | None,
        urls: dict[str, str],
        reattach_inbound: bool,
        manager_comment: str | None = None,
        forwarded_from: str | None = None,
    ) -> PendingOutboundEmail:
        if template_key == "manager.escalation.missing_fields":
            subject = f"[{case.case_number}] Action required — missing invoice fields"
        elif template_key == _VENDOR_NOT_FOUND_TEMPLATE:
            subject = f"[{case.case_number}] Action required — vendor not set up"
        else:
            subject = f"[{case.case_number}] Action required — manager review"

        approve_label = ap_escalation_approve_button_label(escalation.reason_code)
        outbound = PendingOutboundEmail(
            case_id=case.id,
            email_id=email_id,
            mailbox_id=executive.id,
            to_addresses=[escalation.target_email],
            cc_addresses=[],
            subject=subject,
            body_plain=summary,
            message_type="other",
            status="approved",
            metadata_={
                "template": template_key,
                "case_number": case.case_number,
                "escalation_id": str(escalation.id),
                "reason_code": escalation.reason_code,
                "approve_label": approve_label,
                "reattach_inbound_attachments": reattach_inbound,
                "summary": summary,
                "error_reason": error_detail,
                "executive_mailbox": executive.email_address,
                "missing_fields": missing_fields,
                "extracted_fields": extracted_fields,
                "extraction_confidence": extraction_confidence,
                "manager_comment": manager_comment,
                "forwarded_from": forwarded_from,
                **urls,
            },
        )
        self._session.add(outbound)
        await self._session.flush()
        return outbound

    async def escalate_to_manager(
        self,
        *,
        case: Case,
        email: Email | None,
        reason_code: str,
        summary: str,
        error_detail: str,
        actor_name: str,
        actor_type: str = "worker",
        missing_fields: list[str] | None = None,
        extracted_fields: dict[str, str | None] | None = None,
        extraction_confidence: float | None = None,
        escalation_template: str = "manager.escalation.request",
        target_email_override: str | None = None,
        include_escalate: bool | None = None,
        preserve_case_status: bool = False,
        force_reattach_inbound: bool = False,
    ) -> CaseEscalation | None:
        """Step 1: manager review before any sender failure notification."""
        existing = await self._pending_escalation(case.id)
        if existing is not None:
            return existing

        mailbox_address = email.mailbox_address if email else None
        if not mailbox_address and case.email_id:
            linked = await self._cases.get_email(case.email_id)
            mailbox_address = linked.mailbox_address if linked else None
        if not mailbox_address:
            logger.warning("Cannot escalate case %s — no executive mailbox", case.case_number)
            return None

        executive = await self.get_mailbox_for_address(mailbox_address)
        if executive is None:
            logger.warning("No mailbox config for %s", mailbox_address)
            return None

        if target_email_override:
            target_email = target_email_override
        elif executive.escalation_manager_email:
            target_email = executive.escalation_manager_email
        else:
            logger.warning(
                "No escalation_manager_email for mailbox %s", mailbox_address
            )
            return None
        target_mailbox = await self.get_mailbox_for_address(target_email)

        escalation_id = uuid4()
        wire, token_hash, expires = issue_escalation_token(
            escalation_id=escalation_id,
            case_id=case.id,
        )
        missing_fields_list = list(missing_fields or [])
        is_missing_fields = escalation_template == "manager.escalation.missing_fields"
        is_vendor_not_found = (
            reason_code == _REASON_VENDOR_NOT_FOUND
            or escalation_template == _VENDOR_NOT_FOUND_TEMPLATE
        )
        show_escalate = (
            False
            if is_vendor_not_found
            else (
                include_escalate
                if include_escalate is not None
                else (not is_missing_fields)
            )
        )
        urls = self.escalation_action_urls(
            escalation_id,
            wire,
            include_approve=not is_vendor_not_found,
            include_escalate=show_escalate,
            include_request_info=is_missing_fields,
        )

        context: dict = {
            "error_reason": error_detail,
            "actor_name": actor_name,
            "missing_fields": missing_fields_list,
            "extracted_fields": extracted_fields or {},
            "extraction_confidence": extraction_confidence,
            "notification": {
                "template": escalation_template,
                "wire_token": wire,
                **urls,
            },
        }

        source_email_id = email.id if email else case.email_id
        has_inbound_attachments = force_reattach_inbound or (
            await self._inbound_attachment_count(source_email_id) > 0
        )
        if has_inbound_attachments:
            context["notification"]["reattach_inbound_attachments"] = True

        row = CaseEscalation(
            id=escalation_id,
            case_id=case.id,
            email_id=email.id if email else case.email_id,
            originating_mailbox_id=executive.id,
            target_mailbox_id=target_mailbox.id if target_mailbox else None,
            target_email=target_email,
            status="pending",
            reason_code=reason_code,
            summary=summary,
            context=context,
            response_token_hash=token_hash,
            token_expires_at=expires,
        )
        await self._escalations.create(row)

        if not preserve_case_status:
            case.status = "on_hold"
        meta = dict(case.workflow_metadata or {})
        meta.update(
            {
                "escalation_pending": True,
                "escalation_id": str(escalation_id),
                "error_reason": error_detail,
                "reason_code": reason_code,
            }
        )
        if missing_fields_list:
            meta["missing_fields"] = missing_fields_list
        if extracted_fields:
            meta["extracted_fields"] = extracted_fields
        if extraction_confidence is not None:
            meta["extraction_confidence"] = extraction_confidence
        case.workflow_metadata = meta

        await self.log_step(
            action="escalated_to_manager",
            summary=(
                f"[{case.case_number}] Escalated to {target_email}: {summary}"
            ),
            actor_type=actor_type,
            actor_name=actor_name,
            mailbox_id=executive.id,
            case_id=case.id,
            email_id=email.id if email else case.email_id,
            metadata={
                "escalation_id": str(escalation_id),
                "target_email": target_email,
                "reason_code": reason_code,
                "error_reason": error_detail,
                **urls,
            },
        )
        await self._session.flush()

        outbound = await self._queue_manager_escalation_outbound(
            case=case,
            escalation=row,
            executive=executive,
            email_id=source_email_id,
            template_key=escalation_template,
            summary=summary,
            error_detail=error_detail,
            missing_fields=missing_fields_list,
            extracted_fields=extracted_fields or {},
            extraction_confidence=extraction_confidence,
            urls=urls,
            reattach_inbound=has_inbound_attachments,
        )
        smtp_id = await self._outbound.try_send_pending(outbound, source_email=email)
        if smtp_id:
            ctx_meta = dict(row.context or {})
            notif = dict(ctx_meta.get("notification") or {})
            notif["smtp_message_id"] = smtp_id
            notif["outbound_id"] = str(outbound.id)
            notif.pop("last_send_error", None)
            ctx_meta["notification"] = notif
            row.context = ctx_meta
            await self._session.flush()
            await self.log_step(
                action="escalation_email_sent",
                summary=f"[{case.case_number}] Manager escalation email sent to {target_email}",
                actor_type=actor_type,
                actor_name=actor_name,
                mailbox_id=executive.id,
                case_id=case.id,
                email_id=source_email_id,
                metadata={
                    "escalation_id": str(escalation_id),
                    "outbound_id": str(outbound.id),
                    "smtp_message_id": smtp_id,
                    "reattach_inbound_attachments": has_inbound_attachments,
                },
            )

        return row

    async def queue_acknowledgement(
        self,
        *,
        case: Case,
        email: Email,
        actor_name: str = "mail-gateway",
    ) -> PendingOutboundEmail | None:
        """Send ack after case_number exists — separate from error flow (`17` §10.5.1)."""
        if not self.is_external_sender(email.from_address):
            return None

        existing = await self._session.execute(
            select(PendingOutboundEmail)
            .where(
                PendingOutboundEmail.case_id == case.id,
                PendingOutboundEmail.message_type == "acknowledgement",
            )
            .limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return None

        mailbox = await self.get_mailbox_for_address(email.mailbox_address)
        if mailbox is None:
            return None

        subject = f"[{case.case_number}] We received your email"
        if email.subject:
            subject = f"{subject} — {email.subject[:200]}"

        body = (
            f"Thank you for your email. We have received your message and assigned "
            f"reference {case.case_number}. Our team will review it shortly.\n\n"
            f"Original subject: {email.subject or '(no subject)'}"
        )

        outbound = PendingOutboundEmail(
            case_id=case.id,
            email_id=email.id,
            mailbox_id=mailbox.id,
            to_addresses=[email.from_address],
            cc_addresses=[],
            subject=subject,
            body_plain=body,
            message_type="acknowledgement",
            status="approved",
            metadata_={
                "template": "mail.intake.acknowledged",
                "case_number": case.case_number,
                "reattach_inbound_attachments": email.attachment_count > 0,
            },
        )
        self._session.add(outbound)
        await self._session.flush()

        await self.log_step(
            action="ack_sent",
            summary=f"[{case.case_number}] Acknowledgement queued for {email.from_address}",
            actor_type="system",
            actor_name=actor_name,
            mailbox_id=mailbox.id,
            case_id=case.id,
            email_id=email.id,
            metadata={"outbound_id": str(outbound.id), "to": email.from_address},
        )

        smtp_id = await self._outbound.try_send_pending(outbound, source_email=email)
        if smtp_id:
            await self.log_step(
                action="ack_delivered",
                summary=f"[{case.case_number}] Acknowledgement sent to {email.from_address}",
                actor_type="system",
                actor_name=actor_name,
                mailbox_id=mailbox.id,
                case_id=case.id,
                email_id=email.id,
                metadata={"outbound_id": str(outbound.id), "smtp_message_id": smtp_id},
            )
        return outbound

    async def queue_submitter_rejection(
        self,
        *,
        case: Case,
        email: Email,
        reason: str,
        manager_comment: str | None = None,
    ) -> PendingOutboundEmail | None:
        """Notify original submitter after manager reject — internal or external."""
        submitter = (email.from_address or "").strip()
        if not submitter:
            return None

        mailbox = await self.get_mailbox_for_address(email.mailbox_address)
        if mailbox is None:
            return None

        subject = f"[{case.case_number}] Submission rejected — action required"
        body_lines = [
            f"Your submission (reference {case.case_number}) was reviewed and could not be processed.",
            f"Reason: {reason}",
        ]
        if manager_comment:
            body_lines.append(f"Manager note: {manager_comment}")
            body_lines.append(
                "Please address the note above and resubmit if appropriate."
            )
        else:
            body_lines.append(
                "Please contact finance if you need clarification or wish to resubmit."
            )
        body = "\n\n".join(body_lines)

        outbound = PendingOutboundEmail(
            case_id=case.id,
            email_id=email.id,
            mailbox_id=mailbox.id,
            to_addresses=[submitter],
            cc_addresses=[],
            subject=subject,
            body_plain=body,
            message_type="other",
            status="approved",
            metadata_={
                "template": "mail.manager.rejection",
                "case_number": case.case_number,
                "failure_reason": reason,
                "manager_comment": manager_comment,
            },
        )
        self._session.add(outbound)
        await self._session.flush()

        await self.log_step(
            action="submitter_rejection_sent",
            summary=f"[{case.case_number}] Rejection notification queued for {submitter}",
            actor_type="manager",
            actor_name="escalation-reject",
            mailbox_id=mailbox.id,
            case_id=case.id,
            email_id=email.id,
            metadata={"outbound_id": str(outbound.id), "to": submitter},
        )

        smtp_id = await self._outbound.try_send_pending(outbound, source_email=email)
        if smtp_id:
            await self.log_step(
                action="submitter_rejection_delivered",
                summary=f"[{case.case_number}] Rejection sent to {submitter}",
                actor_type="manager",
                actor_name="escalation-reject",
                mailbox_id=mailbox.id,
                case_id=case.id,
                email_id=email.id,
                metadata={"outbound_id": str(outbound.id), "smtp_message_id": smtp_id},
            )
        return outbound

    async def queue_manager_approval_acknowledgement(
        self,
        *,
        case: Case,
        email: Email,
        manager_comment: str | None = None,
    ) -> PendingOutboundEmail | None:
        """Acknowledge manager approval to the original submitter."""
        submitter = (email.from_address or "").strip()
        if not submitter:
            return None

        mailbox = await self.get_mailbox_for_address(email.mailbox_address)
        if mailbox is None:
            return None

        subject = f"[{case.case_number}] Approved — processing will continue"
        body_lines = [
            f"Your submission (reference {case.case_number}) has been approved by our finance team.",
            "We will continue processing your request.",
        ]
        if manager_comment:
            body_lines.append(f"Note: {manager_comment}")
        body = "\n\n".join(body_lines)

        outbound = PendingOutboundEmail(
            case_id=case.id,
            email_id=email.id,
            mailbox_id=mailbox.id,
            to_addresses=[submitter],
            cc_addresses=[],
            subject=subject,
            body_plain=body,
            message_type="other",
            status="approved",
            metadata_={
                "template": "mail.manager.approval_ack",
                "case_number": case.case_number,
                "manager_comment": manager_comment,
            },
        )
        self._session.add(outbound)
        await self._session.flush()

        smtp_id = await self._outbound.try_send_pending(outbound, source_email=email)
        if smtp_id:
            await self.log_step(
                action="manager_approval_ack_delivered",
                summary=f"[{case.case_number}] Approval acknowledgement sent to {submitter}",
                actor_type="manager",
                actor_name="escalation-approve",
                mailbox_id=mailbox.id,
                case_id=case.id,
                email_id=email.id,
                metadata={"outbound_id": str(outbound.id), "smtp_message_id": smtp_id},
            )
        return outbound

    async def dispatch_child_escalation(
        self,
        *,
        case: Case,
        child: CaseEscalation,
        parent: CaseEscalation,
        wire_token: str,
        manager_comment: str | None,
        responder_email: str,
    ) -> None:
        """Forward escalation to next tier with parent manager comment."""
        executive = await self.get_mailbox_by_id(child.originating_mailbox_id)
        if executive is None:
            return

        parent_ctx = dict(parent.context or {})
        template_key = (
            (parent_ctx.get("notification") or {}).get("template")
            or "manager.escalation.request"
        )
        include_request_info = template_key == "manager.escalation.missing_fields"
        urls = self.escalation_action_urls(
            child.id,
            wire_token,
            include_request_info=include_request_info,
        )
        reattach = bool(
            (parent_ctx.get("notification") or {}).get("reattach_inbound_attachments")
        )
        child_ctx = {
            **parent_ctx,
            "forwarded_from": responder_email,
            "manager_comment": manager_comment,
            "parent_escalation_id": str(parent.id),
            "notification": {
                **urls,
                "template": template_key,
                "reattach_inbound_attachments": reattach,
            },
        }
        child.context = child_ctx
        await self._session.flush()

        outbound = await self._queue_manager_escalation_outbound(
            case=case,
            escalation=child,
            executive=executive,
            email_id=child.email_id or case.email_id,
            template_key=template_key,
            summary=child.summary,
            error_detail=parent_ctx.get("error_reason") or child.summary,
            missing_fields=parent_ctx.get("missing_fields") or [],
            extracted_fields=parent_ctx.get("extracted_fields") or {},
            extraction_confidence=parent_ctx.get("extraction_confidence"),
            urls=urls,
            reattach_inbound=reattach,
            manager_comment=manager_comment,
            forwarded_from=responder_email,
        )
        email = None
        if child.email_id or case.email_id:
            email = await self._cases.get_email(child.email_id or case.email_id)
        smtp_id = await self._outbound.try_send_manager_escalation(
            child,
            case=case,
            executive_mailbox=executive,
            source_email=email,
        )
        if smtp_id:
            await self.log_step(
                action="escalation_email_sent",
                summary=f"[{case.case_number}] Escalation forwarded to {child.target_email}",
                actor_type="manager",
                actor_name=responder_email,
                mailbox_id=executive.id,
                case_id=case.id,
                email_id=child.email_id or case.email_id,
                metadata={
                    "escalation_id": str(child.id),
                    "parent_escalation_id": str(parent.id),
                    "outbound_id": str(outbound.id),
                    "smtp_message_id": smtp_id,
                },
            )
        await self.log_step(
            action="escalated",
            summary=f"[{case.case_number}] Escalation forwarded to {child.target_email}",
            actor_type="manager",
            actor_name=responder_email,
            mailbox_id=child.originating_mailbox_id,
            case_id=case.id,
            email_id=child.email_id,
            metadata={
                "parent_escalation_id": str(parent.id),
                "child_escalation_id": str(child.id),
                "target_email": child.target_email,
                "manager_comment": manager_comment,
            },
        )

    async def queue_failure_notification(
        self,
        *,
        case: Case,
        email: Email,
        reason: str,
        manager_comment: str | None = None,
    ) -> PendingOutboundEmail | None:
        """Step 2: only after manager rejects escalation — never before review."""
        if not self.is_external_sender(email.from_address):
            return None

        mailbox = await self.get_mailbox_for_address(email.mailbox_address)
        if mailbox is None:
            return None

        subject = f"[{case.case_number}] Unable to process your email"
        body_lines = [
            f"We were unable to complete processing of your email (reference {case.case_number}).",
            f"Reason: {reason}",
        ]
        if manager_comment:
            body_lines.append(f"Note: {manager_comment}")
        body_lines.append(
            "Please contact us if you need further assistance or wish to resubmit."
        )
        body = "\n\n".join(body_lines)

        outbound = PendingOutboundEmail(
            case_id=case.id,
            email_id=email.id,
            mailbox_id=mailbox.id,
            to_addresses=[email.from_address],
            cc_addresses=[],
            subject=subject,
            body_plain=body,
            message_type="other",
            status="approved",
            metadata_={
                "template": "mail.processing.failure",
                "case_number": case.case_number,
                "failure_reason": reason,
                "manager_comment": manager_comment,
            },
        )
        self._session.add(outbound)
        await self._session.flush()

        await self.log_step(
            action="failure_notification_sent",
            summary=(
                f"[{case.case_number}] Failure notification queued for {email.from_address}"
            ),
            actor_type="manager",
            actor_name="escalation-reject",
            mailbox_id=mailbox.id,
            case_id=case.id,
            email_id=email.id,
            metadata={"outbound_id": str(outbound.id), "reason": reason},
        )

        smtp_id = await self._outbound.try_send_pending(outbound, source_email=email)
        if smtp_id:
            await self.log_step(
                action="failure_notification_delivered",
                summary=f"[{case.case_number}] Failure notification sent to {email.from_address}",
                actor_type="manager",
                actor_name="escalation-reject",
                mailbox_id=mailbox.id,
                case_id=case.id,
                email_id=email.id,
                metadata={"outbound_id": str(outbound.id), "smtp_message_id": smtp_id},
            )
        return outbound

    async def queue_clarification_request(
        self,
        *,
        case: Case,
        email: Email,
        missing_fields: list[str],
        manager_comment: str | None = None,
    ) -> PendingOutboundEmail | None:
        """Queue client clarification after manager selects Request More Info."""
        if not self.is_external_sender(email.from_address):
            return None

        mailbox = await self.get_mailbox_for_address(email.mailbox_address)
        if mailbox is None:
            return None

        field_lines = [f"- {field.replace('_', ' ')}" for field in missing_fields]
        fields_text = "\n".join(field_lines) if field_lines else "- additional invoice details"
        subject = f"[{case.case_number}] Additional information required"
        if email.subject:
            subject = f"{subject} — {email.subject[:200]}"

        body_lines = [
            f"Thank you for your email (reference {case.case_number}).",
            "To complete processing, we need the following information:",
            fields_text,
        ]
        if manager_comment:
            body_lines.append(f"Note from our team: {manager_comment}")
        body_lines.append(
            "Please reply to this email with the missing details or an updated document."
        )
        body = "\n\n".join(body_lines)

        outbound = PendingOutboundEmail(
            case_id=case.id,
            email_id=email.id,
            mailbox_id=mailbox.id,
            to_addresses=[email.from_address],
            cc_addresses=[],
            subject=subject,
            body_plain=body,
            message_type="clarification",
            status="approved",
            metadata_={
                "template": "mail.clarification.request",
                "case_number": case.case_number,
                "missing_fields": missing_fields,
                "source_email_id": str(email.id),
                "manager_comment": manager_comment,
            },
        )
        self._session.add(outbound)
        await self._session.flush()

        await self.log_step(
            action="clarification_sent",
            summary=f"[{case.case_number}] Clarification request queued for {email.from_address}",
            actor_type="manager",
            actor_name="escalation-request-info",
            mailbox_id=mailbox.id,
            case_id=case.id,
            email_id=email.id,
            metadata={
                "outbound_id": str(outbound.id),
                "missing_fields": missing_fields,
            },
        )

        smtp_id = await self._outbound.try_send_pending(outbound, source_email=email)
        if smtp_id:
            await self.log_step(
                action="clarification_delivered",
                summary=f"[{case.case_number}] Clarification sent to {email.from_address}",
                actor_type="manager",
                actor_name="escalation-request-info",
                mailbox_id=mailbox.id,
                case_id=case.id,
                email_id=email.id,
                metadata={"outbound_id": str(outbound.id), "smtp_message_id": smtp_id},
            )
        return outbound

    async def resume_after_manager_approve(
        self,
        *,
        case: Case,
        escalation: CaseEscalation,
        actor_name: str = "manager",
        override_po_check: bool = True,
        override_gl_period: bool = False,
        gl_period_override_reason: str | None = None,
        gl_period_posted_by: str | None = None,
        ap_step_override_key: str | None = None,
    ) -> str | None:
        """Step 3: re-enqueue for reprocessing after manager approval."""
        meta = dict(case.workflow_metadata or {})
        meta.update(
            {
                "escalation_pending": False,
                "manager_decision": "approved",
                "escalation_id": str(escalation.id),
                "reprocess_requested": True,
            }
        )
        if escalation.manager_comment:
            meta["manager_comment"] = escalation.manager_comment
        if override_po_check:
            meta["override_po_check"] = True
        if ap_step_override_key:
            overrides = dict(meta.get("ap_step_overrides") or {})
            overrides[ap_step_override_key] = True
            meta["ap_step_overrides"] = overrides
        if override_gl_period:
            meta["gl_period_override"] = True
            meta["gl_period_override_reason"] = gl_period_override_reason or escalation.manager_comment or "Manager approved GL period override"
            meta["gl_period_posted_by"] = gl_period_posted_by or actor_name
            meta.pop("error_type", None)
            meta.pop("reason_code", None)
        case.workflow_metadata = meta
        case.status = "validation" if ap_step_override_key else "classified"

        email = None
        if case.email_id:
            email = await self._cases.get_email(case.email_id)

        await self.log_step(
            action="manager_approved",
            summary=f"[{case.case_number}] Manager approved escalation — reprocessing",
            actor_type="manager",
            actor_name=actor_name,
            mailbox_id=escalation.originating_mailbox_id,
            case_id=case.id,
            email_id=case.email_id,
            metadata={
                "escalation_id": str(escalation.id),
                "override_po_check": override_po_check,
                "manager_comment": escalation.manager_comment,
            },
        )

        message_id = await enqueue_accounts(
            case_id=case.id,
            case_type=case.type,
            case_number=case.case_number,
            email_id=case.email_id,
            priority=case.priority or "medium",
            stp_eligible=bool(case.stp_eligible),
            confidence_score=float(case.confidence_score or 0),
            source="manager-escalation-approve",
            override_po_check=override_po_check,
            gl_period_override=override_gl_period,
            gl_period_override_reason=meta.get("gl_period_override_reason"),
            gl_period_posted_by=meta.get("gl_period_posted_by"),
        )
        if email is not None:
            await self.queue_manager_approval_acknowledgement(
                case=case,
                email=email,
                manager_comment=escalation.manager_comment,
            )
        await self._session.flush()
        return message_id

    async def log_policy_check(
        self,
        *,
        case: Case,
        mailbox_id: UUID | None,
        passed: bool,
        policy_action: dict,
        actor_name: str,
    ) -> None:
        action = "policy_passed" if passed else "policy_blocked"
        await self.log_step(
            action=action,
            summary=f"[{case.case_number}] Policy check {'passed' if passed else 'blocked'}",
            actor_name=actor_name,
            mailbox_id=mailbox_id,
            case_id=case.id,
            email_id=case.email_id,
            metadata={"policy_action": policy_action},
        )

    async def log_journal_posted(
        self,
        *,
        case: Case,
        mailbox_id: UUID | None,
        journal_entry_id: UUID,
        debits: list[dict],
        credits: list[dict],
        actor_name: str,
    ) -> None:
        await self.log_step(
            action="journal_posted",
            summary=f"[{case.case_number}] Journal entry posted",
            actor_name=actor_name,
            mailbox_id=mailbox_id,
            case_id=case.id,
            email_id=case.email_id,
            metadata={
                "journal_entry_id": str(journal_entry_id),
                "debits": debits,
                "credits": credits,
            },
        )
