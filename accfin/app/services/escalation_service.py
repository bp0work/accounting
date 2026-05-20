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


class EscalationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CaseEscalationRepository(session)
        self._cases = CaseRepository(session)

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
            if case and case.workflow_metadata is not None:
                meta = dict(case.workflow_metadata)
                meta["manager_decision"] = "approved"
                case.workflow_metadata = meta

        elif action == "reject":
            row.status = "rejected"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = comment
            case = await self._cases.get(row.case_id)
            if case:
                case.status = "rejected"

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
