"""Manager escalation respond — `05` §8.8a."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.core.mail_action_token import (
    hash_token,
    issue_escalation_token,
    verify_escalation_token,
)
from app.models.executive_mail import CaseEscalation
from app.repositories.case import CaseRepository
from app.repositories.executive_mail import CaseEscalationRepository
from app.schemas.executive_mail import EscalationRespondResult
from app.services.executive_mail_service import ExecutiveMailService


class EscalationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CaseEscalationRepository(session)
        self._cases = CaseRepository(session)
        self._executive_mail = ExecutiveMailService(session)

    async def respond(
        self,
        escalation_id: UUID,
        *,
        action: str,
        wire_token: str,
        comment: str | None = None,
        responder_email: str | None = None,
    ) -> EscalationRespondResult:
        if action not in ("approve", "reject", "escalate"):
            raise AppHTTPException(400, "VALIDATION_ERROR", "action must be approve, reject, or escalate")

        try:
            verify_escalation_token(wire_token, escalation_id=escalation_id)
        except ValueError as exc:
            code = str(exc)
            raise AppHTTPException(400, code, "Invalid or expired escalation token") from exc

        token_hash = hash_token(wire_token)
        row = await self._repo.get(escalation_id)
        if row is None:
            raise AppHTTPException(404, "NOT_FOUND", "Escalation not found")
        if row.response_token_hash != token_hash:
            raise AppHTTPException(400, "INVALID_ESCALATION_TOKEN", "Token does not match escalation")

        if row.status != "pending":
            if row.status in ("approved", "rejected", "escalated"):
                return EscalationRespondResult(
                    escalation_id=row.id,
                    case_id=row.case_id,
                    action=action,
                    status=row.status,
                    responded_at=row.responded_at or datetime.now(UTC),
                    message="Already responded (idempotent)",
                )
            raise AppHTTPException(409, "ESCALATION_ALREADY_RESPONDED", "Escalation is not pending")

        now = datetime.now(UTC)
        responder = responder_email or row.target_email
        child_id: UUID | None = None
        target_email: str | None = None

        if action == "approve":
            row.status = "approved"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = comment
            case = await self._cases.get(row.case_id)
            if case:
                await self._executive_mail.resume_after_manager_approve(
                    case=case,
                    escalation=row,
                    actor_name=responder,
                )

        elif action == "reject":
            row.status = "rejected"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = comment
            case = await self._cases.get(row.case_id)
            if case:
                case.status = "rejected"
                meta = dict(case.workflow_metadata or {})
                meta["manager_decision"] = "rejected"
                meta["escalation_pending"] = False
                case.workflow_metadata = meta

                email = None
                if row.email_id:
                    email = await self._cases.get_email(row.email_id)
                elif case.email_id:
                    email = await self._cases.get_email(case.email_id)

                error_reason = (row.context or {}).get("error_reason") or row.summary
                if email is not None:
                    await self._executive_mail.queue_failure_notification(
                        case=case,
                        email=email,
                        reason=error_reason,
                        manager_comment=comment,
                    )

                await self._executive_mail.log_step(
                    action="manager_rejected",
                    summary=f"[{case.case_number}] Manager rejected escalation",
                    actor_type="manager",
                    actor_name=responder,
                    mailbox_id=row.originating_mailbox_id,
                    case_id=case.id,
                    email_id=email.id if email else None,
                    metadata={
                        "escalation_id": str(row.id),
                        "manager_comment": comment,
                    },
                )

        elif action == "escalate":
            manager_mailbox = await self._repo.get_mailbox_by_email(row.target_email)
            if manager_mailbox is None or not manager_mailbox.escalation_manager_email:
                raise AppHTTPException(
                    422,
                    "ESCALATION_TIER_EXHAUSTED",
                    "No further escalation tier configured",
                )
            row.status = "escalated"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = comment

            target_email = manager_mailbox.escalation_manager_email
            target_mailbox = await self._repo.get_mailbox_by_email(target_email)
            child_id = uuid4()
            wire, token_hash, expires = issue_escalation_token(
                escalation_id=child_id,
                case_id=row.case_id,
            )
            child = CaseEscalation(
                id=child_id,
                case_id=row.case_id,
                email_id=row.email_id,
                originating_mailbox_id=row.originating_mailbox_id,
                target_mailbox_id=target_mailbox.id if target_mailbox else None,
                target_email=target_email,
                parent_escalation_id=row.id,
                status="pending",
                summary=row.summary,
                context=row.context,
                response_token_hash=token_hash,
                token_expires_at=expires,
            )
            await self._repo.create(child)
            case = await self._cases.get(row.case_id)
            if case:
                await self._executive_mail.log_step(
                    action="escalated",
                    summary=(
                        f"[{case.case_number}] Escalation forwarded to {target_email}"
                    ),
                    actor_type="manager",
                    actor_name=responder,
                    mailbox_id=row.originating_mailbox_id,
                    case_id=case.id,
                    email_id=row.email_id,
                    metadata={
                        "parent_escalation_id": str(row.id),
                        "child_escalation_id": str(child_id),
                        "target_email": target_email,
                    },
                )
            _ = wire  # outbound email dispatch deferred to notification worker

        await self._session.commit()
        return EscalationRespondResult(
            escalation_id=row.id,
            case_id=row.case_id,
            action=action,
            status=row.status,
            child_escalation_id=child_id,
            target_email=target_email,
            responded_at=row.responded_at or now,
        )
