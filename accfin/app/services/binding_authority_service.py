"""Binding authority policy load/save and approval completion — `0.14.9`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.ledger import JournalEntry
from app.models.policy import Approval, Policy
from app.policies.binding_authority import (
    BINDING_AUTHORITY_REASON_PREFIX,
    BindingAuthorityThresholds,
    CASE_TYPE_POLICY_NAMES,
    evaluate_approval_tier,
    policy_name_for_case_type,
    sla_hours_for_tier,
)
from app.repositories.case import CaseRepository
from app.services.executive_mail_service import ExecutiveMailService

POLICY_KEYS = ("ap_approval_thresholds", "ar_approval_thresholds", "expense_approval_thresholds")

DOCUMENT_LABELS: dict[str, str] = {
    "ap_approval_thresholds": "AP Invoice",
    "ar_approval_thresholds": "AR Invoice",
    "expense_approval_thresholds": "Expense Claim",
}

ACCOUNTS_MANAGER_EMAIL = "acc.mmlogistix@bp0.work"
CFO_EMAIL = "cfo.mmlogistix@bp0.work"


def binding_reason_code(tier: int) -> str:
    return f"{BINDING_AUTHORITY_REASON_PREFIX}_TIER{tier}"


class BindingAuthorityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._mail = ExecutiveMailService(session)

    async def get_all_thresholds(self) -> dict[str, BindingAuthorityThresholds]:
        out: dict[str, BindingAuthorityThresholds] = {}
        for name in POLICY_KEYS:
            out[name] = await self.get_thresholds_by_policy_name(name)
        return out

    async def get_thresholds(self, case_type: str) -> BindingAuthorityThresholds:
        name = policy_name_for_case_type(case_type)
        if name is None:
            return BindingAuthorityThresholds.from_rules(None)
        return await self.get_thresholds_by_policy_name(name)

    async def get_thresholds_by_policy_name(self, policy_name: str) -> BindingAuthorityThresholds:
        row = await self._active_policy(policy_name)
        if row is None:
            return BindingAuthorityThresholds.from_rules(None)
        rules = row.rules if isinstance(row.rules, dict) else {}
        return BindingAuthorityThresholds.from_rules(rules)

    async def patch_thresholds(
        self, updates: dict[str, dict]
    ) -> dict[str, BindingAuthorityThresholds]:
        result: dict[str, BindingAuthorityThresholds] = {}
        for policy_name, body in updates.items():
            if policy_name not in POLICY_KEYS:
                continue
            row = await self._active_policy(policy_name)
            if row is None:
                continue
            merged = BindingAuthorityThresholds.from_rules(
                row.rules if isinstance(row.rules, dict) else {}
            ).to_dict()
            merged.update(body)
            row.rules = merged
            result[policy_name] = BindingAuthorityThresholds.from_rules(merged)
        await self._session.flush()
        return result

    async def evaluate_tier(
        self,
        *,
        amount: Decimal | float,
        confidence: float,
        risk_flags: list[str] | None,
        case_type: str,
    ) -> tuple[int, BindingAuthorityThresholds]:
        thresholds = await self.get_thresholds(case_type)
        tier = evaluate_approval_tier(
            amount=amount,
            confidence=confidence,
            risk_flags=risk_flags,
            thresholds=thresholds,
        )
        return tier, thresholds

    async def complete_approval(
        self,
        case: Case,
        *,
        actor_name: str,
        manager_comment: str | None = None,
    ) -> str | None:
        """Post draft journal and mark case posted; notify submitter."""
        journal_id = await self._post_draft_journal(case)
        case.status = "posted"
        case.completed_at = datetime.now(UTC)
        case.current_approval_tier = None
        meta = dict(case.workflow_metadata or {})
        meta["binding_authority_pending"] = False
        meta["manager_decision"] = "approved"
        if manager_comment:
            meta["manager_comment"] = manager_comment
        case.workflow_metadata = meta

        pending = await self._pending_approval_row(case.id)
        if pending:
            pending.status = "approved"
            pending.decided_at = datetime.now(UTC)
            if manager_comment:
                pending.comments = manager_comment

        await self._mail.log_step(
            action="binding_authority_approved",
            summary=f"[{case.case_number}] Binding authority approved — journal posted",
            actor_type="manager",
            actor_name=actor_name,
            case_id=case.id,
            email_id=case.email_id,
            metadata={"journal_entry_id": journal_id},
        )

        email = None
        if case.email_id:
            email = await self._cases.get_email(case.email_id)
        if email is not None:
            await self._mail.queue_manager_approval_acknowledgement(
                case=case,
                email=email,
                manager_comment=manager_comment,
            )
        await self._session.flush()
        return journal_id

    async def reject_case(
        self,
        case: Case,
        *,
        actor_name: str,
        reason: str,
    ) -> None:
        case.status = "rejected"
        meta = dict(case.workflow_metadata or {})
        meta["binding_authority_pending"] = False
        meta["manager_decision"] = "rejected"
        meta["manager_comment"] = reason
        case.workflow_metadata = meta

        pending = await self._pending_approval_row(case.id)
        if pending:
            pending.status = "rejected"
            pending.decided_at = datetime.now(UTC)
            pending.comments = reason

        email = None
        if case.email_id:
            email = await self._cases.get_email(case.email_id)
        if email is not None:
            await self._mail.queue_submitter_rejection(
                case=case,
                email=email,
                reason="Your submission was rejected by the approver.",
                manager_comment=reason,
            )
        await self._mail.log_step(
            action="binding_authority_rejected",
            summary=f"[{case.case_number}] Binding authority rejected",
            actor_type="manager",
            actor_name=actor_name,
            case_id=case.id,
            email_id=case.email_id,
            metadata={"reason": reason},
        )
        await self._session.flush()

    async def escalate_tier2_to_cfo(self, case: Case, *, actor_name: str, comment: str | None) -> None:
        meta = dict(case.workflow_metadata or {})
        meta["binding_escalated_to_cfo"] = True
        meta["policy_tier"] = 3
        meta["binding_authority_tier"] = 3
        if comment:
            meta["manager_comment"] = comment
        case.workflow_metadata = meta
        case.current_approval_tier = 3

        pending = await self._pending_approval_row(case.id)
        if pending:
            pending.tier = 3
            pending.status = "escalated"
            pending.comments = comment or pending.comments

        await self._mail.log_step(
            action="binding_authority_escalated_cfo",
            summary=f"[{case.case_number}] Escalated to CFO for binding authority approval",
            actor_type="manager",
            actor_name=actor_name,
            case_id=case.id,
            email_id=case.email_id,
        )
        await self._session.flush()

    def target_email_for_tier(self, tier: int, *, escalated_to_cfo: bool = False) -> str:
        if tier >= 3 or escalated_to_cfo:
            return CFO_EMAIL
        return ACCOUNTS_MANAGER_EMAIL

    async def _active_policy(self, name: str) -> Policy | None:
        result = await self._session.execute(
            select(Policy)
            .where(Policy.name == name, Policy.is_active.is_(True))
            .order_by(Policy.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _pending_approval_row(self, case_id: UUID) -> Approval | None:
        result = await self._session.execute(
            select(Approval)
            .where(Approval.case_id == case_id, Approval.status == "pending")
            .order_by(Approval.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _post_draft_journal(self, case: Case) -> str | None:
        result = await self._session.execute(
            select(JournalEntry)
            .where(JournalEntry.case_id == case.id, JournalEntry.status == "draft")
            .order_by(JournalEntry.created_at.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            return None
        entry.status = "posted"
        entry.posted_at = datetime.now(UTC)
        entry.posting_date = entry.entry_date
        await self._session.flush()
        return str(entry.id)


def apply_binding_sla(case: Case, tier: int, thresholds: BindingAuthorityThresholds) -> None:
    hours = sla_hours_for_tier(tier, thresholds)
    if hours > 0:
        case.sla_deadline = datetime.now(UTC) + timedelta(hours=hours)
        case.sla_status = "on_track"
