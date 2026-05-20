"""Approval request scaffold — `17` §4.3 (Orchestrator contract)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Approval
from app.repositories.case import CaseRepository


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)

    async def request_approval(
        self,
        *,
        case_id: UUID,
        tier: int,
        amount_value: Decimal | None = None,
        amount_currency: str = "SGD",
        comments: str | None = None,
    ) -> Approval:
        case = await self._cases.get(case_id)
        if case is None:
            raise ValueError(f"Case not found: {case_id}")

        approval = Approval(
            case_id=case_id,
            tier=tier,
            status="pending",
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
        return approval
