"""Approval persistence — `05` §7."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.case import Case
from app.models.policy import Approval
from app.models.user import User


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, approval_id: UUID) -> Approval | None:
        result = await self._session.execute(select(Approval).where(Approval.id == approval_id))
        return result.scalar_one_or_none()

    async def list_approvals(
        self,
        *,
        status: str | None = None,
        tier: int | None = None,
        case_id: UUID | None = None,
        approver_id: UUID | None = None,
        my_pending_user_id: UUID | None = None,
        binding_queue: str | None = None,
        role_name: str | None = None,
        limit: int = 50,
    ) -> list[tuple[Approval, Case]]:
        q = (
            select(Approval, Case)
            .join(Case, Case.id == Approval.case_id)
            .order_by(Approval.created_at.desc())
            .limit(limit)
        )
        if status:
            q = q.where(Approval.status == status)
        if tier is not None:
            q = q.where(Approval.tier == tier)
        if case_id:
            q = q.where(Approval.case_id == case_id)
        if approver_id:
            q = q.where(Approval.approver_id == approver_id)
        if my_pending_user_id:
            q = q.where(
                Approval.status == "pending",
                or_(
                    Approval.approver_id == my_pending_user_id,
                    Approval.approver_id.is_(None),
                ),
            )
        if binding_queue == "acc" or (
            binding_queue is None
            and role_name in ("accounts_clerk", "finance_officer", "finance_manager")
        ):
            q = q.where(
                Approval.status == "pending",
                Approval.tier == 2,
                ~Case.workflow_metadata.contains({"binding_escalated_to_cfo": True}),
            )
        elif binding_queue == "cfo" or (
            binding_queue is None and role_name in ("cfo", "finance_director")
        ):
            q = q.where(
                Approval.status == "pending",
                or_(
                    Approval.tier >= 3,
                    Case.workflow_metadata.contains({"binding_escalated_to_cfo": True}),
                ),
            )
        result = await self._session.execute(q)
        return list(result.all())

    async def get_user(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)
