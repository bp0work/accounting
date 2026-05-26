"""Approval workflow — `05` §7, `17` §4.3."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.models.ledger import JournalEntry
from app.models.policy import Approval
from app.repositories.approval import ApprovalRepository
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.services.audit_service import AuditService
from app.services.binding_authority_service import BindingAuthorityService
from app.services.case_service import CaseService
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.event_bus import publish_user_event
from fastapi import status

TIER2_ROLES = frozenset({"accounts_clerk", "finance_officer"})
EXECUTIVE_ROLES = frozenset({"cfo", "finance_manager"})


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._approvals = ApprovalRepository(session)
        self._cases_service = CaseService(session)
        self._notify = NotificationDispatcher(session)
        self._audit = AuditService(session)

    async def request_approval(
        self,
        *,
        case_id: UUID,
        tier: int,
        amount_value: Decimal | None = None,
        amount_currency: str = "SGD",
        comments: str | None = None,
        approver_id: UUID | None = None,
    ) -> Approval:
        case = await self._cases.get(case_id)
        if case is None:
            raise ValueError(f"Case not found: {case_id}")

        approval = Approval(
            case_id=case_id,
            tier=tier,
            status="pending",
            approver_id=approver_id,
            amount_value=amount_value,
            amount_currency=amount_currency,
            comments=comments,
        )
        self._session.add(approval)
        case.status = "pending_approval"
        case.current_approval_tier = tier
        if amount_value is not None:
            case.amount_value = amount_value
            case.amount_currency = amount_currency
        case.sla_deadline = datetime.now(UTC) + timedelta(hours=24 * tier)
        case.sla_status = "on_track"
        await self._session.flush()

        if approver_id:
            await self._notify.notify_approval_requested(
                approver_id=approver_id,
                approval_id=approval.id,
                case_id=case.id,
                case_number=case.case_number,
                subject=case.subject or case.case_number,
            )
        return approval

    async def approve(
        self,
        approval_id: UUID,
        user: TokenData,
        *,
        note: str | None = None,
        journal_entry_id: UUID | None = None,
    ) -> Approval:
        approval, case = await self._load_approval_case(approval_id)
        self._ensure_can_act(approval, case, user)
        if approval.status != "pending":
            raise AppHTTPException(status.HTTP_409_CONFLICT, "ALREADY_RESPONDED", "Approval already responded")

        meta = case.workflow_metadata or {}
        if meta.get("binding_authority_pending") and case.status == "pending_approval":
            binding = BindingAuthorityService(self._session)
            jid = await binding.complete_approval(
                case,
                actor_name=user.username or str(user.user_id),
                manager_comment=note,
            )
            approval.status = "approved"
            approval.decided_at = datetime.now(UTC)
            approval.comments = note or approval.comments
            approval.approver_id = user.user_id
            if jid:
                approval.journal_entry_id = UUID(jid)
        else:
            approval.status = "approved"
            approval.decided_at = datetime.now(UTC)
            approval.comments = note or approval.comments
            approval.approver_id = user.user_id
            if journal_entry_id:
                approval.journal_entry_id = journal_entry_id

            await self._cases_service.transition_case(
                case.id, "approved", user=user, context={"user": user, "policy_pass": True}
            )
            await self._post_draft_journal(case.id, user.user_id)

        await self._session.flush()

        await publish_user_event(
            str(user.user_id),
            "approval.approved",
            {
                "approval_id": str(approval.id),
                "case_id": str(case.id),
                "case_number": case.case_number,
            },
        )
        await self._audit.record(
            action="approve",
            entity_type="approval",
            entity_id=approval.id,
            case_id=case.id,
            case_number=case.case_number,
            user_id=user.user_id,
            before_state={"status": "pending"},
            after_state={"status": "approved"},
            metadata={"note": note, "journal_entry_id": str(journal_entry_id) if journal_entry_id else None},
        )
        return approval

    async def reject(
        self,
        approval_id: UUID,
        user: TokenData,
        *,
        reason: str,
        return_to: str | None = "manual_review",
    ) -> Approval:
        approval, case = await self._load_approval_case(approval_id)
        self._ensure_can_act(approval, case, user)
        if approval.status != "pending":
            raise AppHTTPException(status.HTTP_409_CONFLICT, "ALREADY_RESPONDED", "Approval already responded")

        meta = case.workflow_metadata or {}
        if meta.get("binding_authority_pending") and case.status == "pending_approval":
            binding = BindingAuthorityService(self._session)
            await binding.reject_case(
                case,
                actor_name=user.username or str(user.user_id),
                reason=reason,
            )
            approval.status = "rejected"
            approval.decided_at = datetime.now(UTC)
            approval.comments = reason
            approval.approver_id = user.user_id
        else:
            approval.status = "rejected"
            approval.decided_at = datetime.now(UTC)
            approval.comments = reason

            await self._cases_service.transition_case(
                case.id, "rejected", user=user, context={"user": user, "policy_pass": True}
            )
            if return_to == "manual_review" and case.status == "rejected":
                case.status = "manual_review"
        await self._session.flush()

        await publish_user_event(
            str(user.user_id),
            "approval.rejected",
            {
                "approval_id": str(approval.id),
                "case_id": str(case.id),
                "case_number": case.case_number,
                "reason": reason,
            },
        )
        await self._audit.record(
            action="reject",
            entity_type="approval",
            entity_id=approval.id,
            case_id=case.id,
            case_number=case.case_number,
            user_id=user.user_id,
            before_state={"status": "pending"},
            after_state={"status": "rejected"},
            metadata={"reason": reason, "return_to": return_to},
        )
        return approval

    async def _load_approval_case(self, approval_id: UUID) -> tuple[Approval, object]:
        approval = await self._approvals.get(approval_id)
        if approval is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Approval not found")
        case = await self._cases.get(approval.case_id)
        if case is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found")
        return approval, case

    async def escalate_to_cfo(
        self,
        approval_id: UUID,
        user: TokenData,
        *,
        note: str | None = None,
    ) -> Approval:
        approval, case = await self._load_approval_case(approval_id)
        self._ensure_can_act(approval, case, user, allow_escalate=True)
        if approval.status != "pending":
            raise AppHTTPException(status.HTTP_409_CONFLICT, "ALREADY_RESPONDED", "Approval already responded")
        if approval.tier != 2:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_TIER",
                "Only Tier 2 approvals can be escalated to CFO",
            )

        binding = BindingAuthorityService(self._session)
        await binding.escalate_tier2_to_cfo(
            case,
            actor_name=user.username or str(user.user_id),
            comment=note,
        )
        approval.tier = 3
        approval.status = "pending"
        approval.comments = note or approval.comments
        await self._session.flush()

        from workers.common.binding_authority_escalation import route_binding_authority_escalation

        email = await self._cases.get_email(case.email_id) if case.email_id else None
        extracted = (case.workflow_metadata or {}).get("extracted_fields") or {}
        await route_binding_authority_escalation(
            self._session,
            case,
            email=email,
            tier=3,
            amount=case.amount_value or Decimal("0"),
            currency=case.amount_currency or "SGD",
            extracted_fields=extracted if isinstance(extracted, dict) else None,
            extraction_confidence=float(
                (case.workflow_metadata or {}).get("extraction_confidence") or 0
            ),
            actor_name=user.username or "finance-ui",
        )
        await self._session.flush()
        return approval

    def _ensure_can_act(
        self,
        approval: Approval,
        case,
        user: TokenData,
        *,
        allow_escalate: bool = False,
    ) -> None:
        if "approvals:approve" not in user.permissions and "approvals:admin" not in user.permissions:
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "INSUFFICIENT_PERMISSION",
                "approvals:approve required",
            )
        if approval.approver_id and approval.approver_id != user.user_id:
            if "approvals:admin" not in user.permissions:
                raise AppHTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "UNAUTHORIZED_APPROVER",
                    "You are not the designated approver",
                )

        role = (user.role_name or "").lower()
        meta = case.workflow_metadata or {}
        escalated = bool(meta.get("binding_escalated_to_cfo"))
        tier = approval.tier

        if allow_escalate:
            if role not in TIER2_ROLES and "approvals:admin" not in user.permissions:
                raise AppHTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "FORBIDDEN",
                    "Only Accounts Manager may escalate to CFO",
                )
            return

        if role in EXECUTIVE_ROLES or "approvals:admin" in user.permissions:
            return
        if role in TIER2_ROLES and tier == 2 and not escalated:
            return
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Your role cannot act on this approval tier",
        )

    async def _post_draft_journal(self, case_id: UUID, user_id: UUID) -> None:
        result = await self._session.execute(
            select(JournalEntry)
            .where(JournalEntry.case_id == case_id, JournalEntry.status == "draft")
            .order_by(JournalEntry.created_at.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            return
        entry.status = "posted"
        entry.posted_at = datetime.now(UTC)
        entry.posted_by = user_id
        entry.posting_date = entry.entry_date
        case = await self._cases.get(case_id)
        if case and case.status == "approved":
            try:
                await self._cases_service.transition_case(
                    case_id, "journal_posted", user=None, context={}
                )
            except AppHTTPException:
                case.status = "posted"
        await self._session.flush()
