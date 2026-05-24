"""Executive email SOP — `01` §6.8, `17` §10.3–§10.5."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.mail_action_token import issue_escalation_token
from app.models.case import Case
from app.models.executive_mail import CaseEscalation, PendingOutboundEmail
from app.models.mail import Email, MailGatewayConfig
from app.repositories.case import CaseRepository
from app.repositories.executive_mail import CaseEscalationRepository
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.finance_activity_log_service import FinanceActivityLogService
from app.services.outbound_mail_service import OutboundMailService
from app.services.queue_router import enqueue_accounts

logger = logging.getLogger(__name__)

INTERNAL_DOMAIN = "@bp0.work"


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

    def escalation_action_urls(self, escalation_id: UUID, wire_token: str) -> dict[str, str]:
        base = self._settings.edge_public_base_url.rstrip("/")
        qs = f"token={wire_token}"
        path = f"/mail/escalations/{escalation_id}/respond"
        return {
            "approve_url": f"{base}{path}?action=approve&{qs}",
            "reject_url": f"{base}{path}?action=reject&{qs}",
            "escalate_url": f"{base}{path}?action=escalate&{qs}",
        }

    async def _pending_escalation(self, case_id: UUID) -> CaseEscalation | None:
        result = await self._session.execute(
            select(CaseEscalation)
            .where(CaseEscalation.case_id == case_id, CaseEscalation.status == "pending")
            .limit(1)
        )
        return result.scalar_one_or_none()

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
        if executive is None or not executive.escalation_manager_email:
            logger.warning(
                "No escalation_manager_email for mailbox %s", mailbox_address
            )
            return None

        target_email = executive.escalation_manager_email
        target_mailbox = await self.get_mailbox_for_address(target_email)

        escalation_id = uuid4()
        wire, token_hash, expires = issue_escalation_token(
            escalation_id=escalation_id,
            case_id=case.id,
        )
        urls = self.escalation_action_urls(escalation_id, wire)

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
            context={
                "error_reason": error_detail,
                "actor_name": actor_name,
                "notification": {
                    "template": "manager.escalation.request",
                    "wire_token": wire,
                    **urls,
                },
            },
            response_token_hash=token_hash,
            token_expires_at=expires,
        )
        await self._escalations.create(row)

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

        smtp_id = await self._outbound.try_send_manager_escalation(
            row,
            case=case,
            executive_mailbox=executive,
            source_email=email,
        )
        if smtp_id:
            await self.log_step(
                action="escalation_email_sent",
                summary=f"[{case.case_number}] Manager escalation email sent to {target_email}",
                actor_type=actor_type,
                actor_name=actor_name,
                mailbox_id=executive.id,
                case_id=case.id,
                email_id=email.id if email else case.email_id,
                metadata={"escalation_id": str(escalation_id), "smtp_message_id": smtp_id},
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

    async def resume_after_manager_approve(
        self,
        *,
        case: Case,
        escalation: CaseEscalation,
        actor_name: str = "manager",
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
        case.workflow_metadata = meta
        case.status = "classified"

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
            metadata={"escalation_id": str(escalation.id)},
        )

        message_id = await enqueue_accounts(
            case_id=case.id,
            case_type=case.type,
            case_number=case.case_number,
            email_id=case.email_id,
            priority=case.priority or "medium",
            stp_eligible=bool(case.stp_eligible),
            confidence_score=float(case.confidence_score or 0),
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
