"""Case lifecycle with state machine persistence — `08` §12.2."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.core.state_machine import CaseStateMachine, TransitionResult
from app.policies.engine import PolicyEngine
from app.repositories.case import CaseRepository
from app.repositories.policy import PolicyRepository
from fastapi import status

from app.schemas.auth import TokenData
from app.schemas.case import CaseRetryResponse
from app.services.queue_router import enqueue_accounts

RETRYABLE_STATUSES = frozenset({"exception", "manual_review"})


@dataclass
class ActorContext:
    permissions: list[str]
    user_id: UUID | None = None
    display_name: str = "system"


class CaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._policies = PolicyRepository(session)
        self._machine = CaseStateMachine()
        self._policy_engine = PolicyEngine()

    async def get_case(self, case_id: UUID):
        case = await self._cases.get(case_id)
        if not case:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found")
        return case

    async def list_cases(
        self,
        *,
        limit: int = 50,
        status_filter: str | None = None,
        date_from=None,
        date_to=None,
    ):
        return await self._cases.list_cases(
            limit=limit,
            status=status_filter,
            date_from=date_from,
            date_to=date_to,
        )

    def _actor_from_token(self, user: TokenData | None) -> ActorContext | None:
        if user is None:
            return None
        return ActorContext(permissions=user.permissions, user_id=user.user_id)

    async def evaluate_policies(self, case) -> dict:
        context = {
            "case": {
                "type": case.type,
                "status": case.status,
                "amount_value": float(case.amount_value) if case.amount_value else None,
                "risk_flags": case.risk_flags or [],
            }
        }
        policies = await self._policies.list_active(policy_type="approval")
        results = [
            self._policy_engine.evaluate_policy(
                {
                    "rules": p.rules,
                    "default_action": {"type": "require_approval", "tier": 2},
                },
                context,
            )
            for p in policies
        ]
        return self._policy_engine.combine_results(results) if results else {
            "type": "require_approval",
            "tier": 2,
        }

    async def transition_case(
        self,
        case_id: UUID,
        trigger: str,
        *,
        user: TokenData | None = None,
        context: dict | None = None,
    ) -> TransitionResult:
        case = await self.get_case(case_id)
        instance = case.workflow_instance
        ctx = dict(context or {})
        if instance:
            ctx["workflow"] = instance

        actor = self._actor_from_token(user)
        policy_action = await self.evaluate_policies(case)
        ctx["policy_pass"] = policy_action.get("type") == "auto_release"

        result = self._machine.transition(
            case,
            trigger,
            actor=actor,
            context=ctx,
        )
        if not result.success:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_TRANSITION",
                result.guard_failed or "Transition not allowed",
            )

        if instance is not None and result.to_state:
            await self._cases.record_transition(
                instance=instance,
                from_state=result.from_state.value,
                to_state=result.to_state.value,
                trigger=trigger,
                actor=str(user.user_id) if user else "system",
                metadata={"policy_action": policy_action},
            )
            await self._cases.add_timeline(
                case_id=case.id,
                event_type="status_changed",
                from_status=result.from_state.value,
                to_status=result.to_state.value,
                actor=str(user.user_id) if user else "system",
                description=f"Trigger: {trigger}",
                actor_user_id=user.user_id if user else None,
            )

        await self._session.commit()
        await self._session.refresh(case)
        return result

    async def retry_case(self, case_id: UUID, *, user: TokenData) -> CaseRetryResponse:
        case = await self.get_case(case_id)
        if case.status not in RETRYABLE_STATUSES:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "CASE_NOT_RETRYABLE",
                f"Case in status '{case.status}' cannot be retried; "
                f"allowed: {', '.join(sorted(RETRYABLE_STATUSES))}",
            )

        previous_status = case.status
        meta = dict(case.workflow_metadata or {})
        for key in ("error_message", "error_reason", "error_type", "reason_code", "reason"):
            meta.pop(key, None)
        meta.update(
            {
                "current_stage": "processing",
                "reprocess_requested": True,
                "manual_retry": True,
            }
        )
        case.workflow_metadata = meta
        case.status = "classified"

        message_id = await enqueue_accounts(
            case_id=case.id,
            case_type=case.type,
            case_number=case.case_number,
            email_id=case.email_id,
            priority=case.priority or "medium",
            stp_eligible=bool(case.stp_eligible),
            confidence_score=float(case.confidence_score or 0),
            source="case-retry",
        )

        await self._cases.add_timeline(
            case_id=case.id,
            event_type="case_retry",
            from_status=previous_status,
            to_status="classified",
            actor=str(user.user_id),
            description="Manual retry — requeued to accounts_queue",
            metadata={"queue_message_id": message_id},
            actor_user_id=user.user_id,
        )

        await self._session.commit()
        await self._session.refresh(case)

        return CaseRetryResponse(
            case_id=case.id,
            case_number=case.case_number,
            message_id=message_id,
            status=case.status,
            previous_status=previous_status,
        )
