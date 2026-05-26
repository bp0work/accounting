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
from app.schemas.executive_mail import EscalationRespondContext, EscalationRespondResult
from app.services.executive_mail_service import ExecutiveMailService


class EscalationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CaseEscalationRepository(session)
        self._cases = CaseRepository(session)
        self._executive_mail = ExecutiveMailService(session)

    async def get_case_number(self, case_id: UUID) -> str | None:
        case = await self._cases.get(case_id)
        return case.case_number if case else None

    def _validate_token(self, wire_token: str, escalation_id: UUID) -> str:
        try:
            verify_escalation_token(wire_token, escalation_id=escalation_id)
        except ValueError as exc:
            code = str(exc)
            raise AppHTTPException(400, code, "Invalid or expired escalation token") from exc
        return hash_token(wire_token)

    async def get_respond_context(
        self,
        escalation_id: UUID,
        *,
        action: str,
        wire_token: str,
    ) -> EscalationRespondContext:
        if action not in ("approve", "reject", "escalate", "request_info"):
            raise AppHTTPException(
                422,
                "INVALID_ESCALATION_ACTION",
                "action must be approve, reject, escalate, or request_info",
            )

        token_hash = self._validate_token(wire_token, escalation_id)
        row = await self._repo.get(escalation_id)
        if row is None:
            raise AppHTTPException(404, "ESCALATION_NOT_FOUND", "Escalation not found")
        if row.response_token_hash != token_hash:
            raise AppHTTPException(400, "INVALID_ESCALATION_TOKEN", "Token does not match escalation")

        case = await self._cases.get(row.case_id)
        case_number = case.case_number if case else str(row.case_id)

        if row.status != "pending":
            return EscalationRespondContext(
                escalation_id=row.id,
                case_id=row.case_id,
                case_number=case_number,
                action=action,
                status=row.status,
                already_responded=True,
                result=EscalationRespondResult(
                    escalation_id=row.id,
                    case_id=row.case_id,
                    action=action,
                    status=row.status,
                    responded_at=row.responded_at or datetime.now(UTC),
                    manager_comment=row.manager_comment,
                    message="Already responded (idempotent)",
                ),
            )

        return EscalationRespondContext(
            escalation_id=row.id,
            case_id=row.case_id,
            case_number=case_number,
            action=action,
            status=row.status,
            already_responded=False,
        )

    async def respond(
        self,
        escalation_id: UUID,
        *,
        action: str,
        wire_token: str,
        comment: str | None = None,
        responder_email: str | None = None,
    ) -> EscalationRespondResult:
        if action not in ("approve", "reject", "escalate", "request_info"):
            raise AppHTTPException(
                422,
                "INVALID_ESCALATION_ACTION",
                "action must be approve, reject, escalate, or request_info",
            )

        token_hash = self._validate_token(wire_token, escalation_id)
        row = await self._repo.get(escalation_id)
        if row is None:
            raise AppHTTPException(404, "ESCALATION_NOT_FOUND", "Escalation not found")
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
                    manager_comment=row.manager_comment,
                    message="Already responded (idempotent)",
                )
            raise AppHTTPException(409, "ESCALATION_ALREADY_RESPONDED", "Escalation is not pending")

        trimmed_comment = (comment or "").strip() or None
        now = datetime.now(UTC)
        responder = responder_email or row.target_email
        child_id: UUID | None = None
        target_email: str | None = None
        message: str | None = None

        if action == "approve":
            row.status = "approved"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment
            case = await self._cases.get(row.case_id)
            if case:
                ctx = row.context or {}
                reason_code = ctx.get("reason_code") or (case.workflow_metadata or {}).get(
                    "reason_code"
                )
                period_closed = reason_code == "PERIOD_CLOSED"
                await self._executive_mail.resume_after_manager_approve(
                    case=case,
                    escalation=row,
                    actor_name=responder,
                    override_po_check=reason_code != "PERIOD_CLOSED",
                    override_gl_period=period_closed,
                    gl_period_override_reason=trimmed_comment
                    or "Manager approved GL period override",
                    gl_period_posted_by=responder,
                )
                message = "Approved. Case requeued for processing and submitter notified."

        elif action == "reject":
            row.status = "rejected"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment
            case = await self._cases.get(row.case_id)
            if case:
                case.status = "rejected"
                meta = dict(case.workflow_metadata or {})
                meta["manager_decision"] = "rejected"
                meta["escalation_pending"] = False
                if trimmed_comment:
                    meta["manager_comment"] = trimmed_comment
                case.workflow_metadata = meta

                email = await self._resolve_email(row, case)
                error_reason = (row.context or {}).get("error_reason") or row.summary
                if email is not None:
                    await self._executive_mail.queue_submitter_rejection(
                        case=case,
                        email=email,
                        reason=error_reason,
                        manager_comment=trimmed_comment,
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
                        "manager_comment": trimmed_comment,
                    },
                )
                message = "Rejected. Submitter has been notified."

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
            row.manager_comment = trimmed_comment

            target_email = manager_mailbox.escalation_manager_email
            target_mailbox = await self._repo.get_mailbox_by_email(target_email)
            child_id = uuid4()
            wire, child_token_hash, expires = issue_escalation_token(
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
                context=dict(row.context or {}),
                response_token_hash=child_token_hash,
                token_expires_at=expires,
            )
            await self._repo.create(child)
            case = await self._cases.get(row.case_id)
            if case:
                await self._executive_mail.dispatch_child_escalation(
                    case=case,
                    child=child,
                    parent=row,
                    wire_token=wire,
                    manager_comment=trimmed_comment,
                    responder_email=responder,
                )
                message = f"Escalated to {target_email}. A new email has been sent."

        elif action == "request_info":
            row.status = "approved"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment
            case = await self._cases.get(row.case_id)
            if case:
                meta = dict(case.workflow_metadata or {})
                meta["manager_decision"] = "request_info"
                meta["clarification_pending"] = True
                meta["escalation_pending"] = False
                if trimmed_comment:
                    meta["manager_comment"] = trimmed_comment
                case.workflow_metadata = meta
                case.status = "on_hold"

                email = await self._resolve_email(row, case)
                missing_fields = (row.context or {}).get("missing_fields") or []
                if email is not None:
                    await self._executive_mail.queue_clarification_request(
                        case=case,
                        email=email,
                        missing_fields=missing_fields,
                        manager_comment=trimmed_comment,
                    )

                await self._executive_mail.log_step(
                    action="manager_request_info",
                    summary=f"[{case.case_number}] Manager requested more information from client",
                    actor_type="manager",
                    actor_name=responder,
                    mailbox_id=row.originating_mailbox_id,
                    case_id=case.id,
                    email_id=email.id if email else None,
                    metadata={
                        "escalation_id": str(row.id),
                        "missing_fields": missing_fields,
                        "manager_comment": trimmed_comment,
                    },
                )
                message = "Request for more information sent to the client."

        await self._session.commit()
        return EscalationRespondResult(
            escalation_id=row.id,
            case_id=row.case_id,
            action=action,
            status=row.status,
            child_escalation_id=child_id,
            target_email=target_email,
            responded_at=row.responded_at or now,
            manager_comment=trimmed_comment,
            message=message,
        )

    async def _resolve_email(self, row: CaseEscalation, case):
        if row.email_id:
            return await self._cases.get_email(row.email_id)
        if case.email_id:
            return await self._cases.get_email(case.email_id)
        return None
