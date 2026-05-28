"""Case lifecycle with state machine persistence — `08` §12.2."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.exceptions import AppHTTPException
from app.core.state_machine import CaseStateMachine, TransitionResult
from app.models.accounting_period import AccountingPeriod
from app.policies.engine import PolicyEngine
from app.repositories.case import CaseRepository
from app.repositories.policy import PolicyRepository
from fastapi import status

from app.schemas.auth import TokenData
from app.schemas.case import CaseRetryResponse
from app.services.queue_router import enqueue_accounts
from app.services.wasabi_archive import WasabiArchiveService

RETRYABLE_STATUSES = frozenset({"exception", "manual_review"})
RETRYABLE_HERMES_ON_HOLD_CODES = frozenset({"HERMES_TIMEOUT", "HERMES_UNAVAILABLE"})


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

    async def on_case_linked_to_email(self, case, email_id: UUID) -> dict[str, int | str]:
        """Post-intake hook: archive email attachments to Wasabi when configured."""
        archive = WasabiArchiveService(self._session)
        return await archive.archive_email_attachments(
            case_number=case.case_number,
            email_id=email_id,
        )

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

    async def _period_closed_hold_retryable(
        self, case, *, session: AsyncSession | None = None
    ) -> bool:
        if case.status != "on_hold":
            return False
        meta = case.workflow_metadata or {}
        if meta.get("reason_code") != "PERIOD_CLOSED" and meta.get("error_type") != "PERIOD_CLOSED":
            return False
        period_id = meta.get("gl_period_id")
        if not period_id:
            return False
        try:
            pid = UUID(str(period_id))
        except (TypeError, ValueError):
            return False
        db = session or self._session
        period = await db.get(AccountingPeriod, pid)
        return period is not None and period.status != "closed"

    async def _transient_hermes_hold_retryable(self, case) -> bool:
        if case.status != "on_hold":
            return False
        meta = case.workflow_metadata or {}
        error_code = str(meta.get("error_code") or "").strip().upper()
        return error_code in RETRYABLE_HERMES_ON_HOLD_CODES

    async def retry_case(self, case_id: UUID, *, user: TokenData) -> CaseRetryResponse:
        """
        Requeue a case for worker processing.

        DB writes run in a dedicated session and commit before Redis enqueue
        (same phased pattern as accounts-worker classification — no ORM use
        across external awaits).
        """
        factory = get_session_factory()
        message_id = str(uuid4())
        previous_status: str
        case_id_val: UUID
        case_number: str
        case_type: str
        email_id: UUID | None
        priority: str
        stp_eligible: bool
        confidence_score: float

        async with factory() as session:
            cases = CaseRepository(session)
            case = await cases.get(case_id)
            if case is None:
                raise AppHTTPException(
                    status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found"
                )

            retryable = case.status in RETRYABLE_STATUSES
            if not retryable:
                retryable = await self._period_closed_hold_retryable(case, session=session)
            if not retryable:
                retryable = await self._transient_hermes_hold_retryable(case)
            if not retryable:
                raise AppHTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "CASE_NOT_RETRYABLE",
                    f"Case in status '{case.status}' cannot be retried; "
                    f"allowed: {', '.join(sorted(RETRYABLE_STATUSES))}, "
                    f"or on_hold after GL period reopen, "
                    f"or on_hold with transient Hermes errors "
                    f"({', '.join(sorted(RETRYABLE_HERMES_ON_HOLD_CODES))})",
                )

            previous_status = case.status
            case_id_val = case.id
            case_number = case.case_number
            case_type = case.type
            email_id = case.email_id
            priority = case.priority or "medium"
            stp_eligible = bool(case.stp_eligible)
            confidence_score = float(case.confidence_score or 0)

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

            await cases.add_timeline(
                case_id=case_id_val,
                event_type="case_retry",
                from_status=previous_status,
                to_status="classified",
                actor=str(user.user_id),
                description="Manual retry — requeued to accounts_queue",
                metadata={"queue_message_id": message_id},
                actor_user_id=user.user_id,
            )
            await session.commit()

        await enqueue_accounts(
            case_id=case_id_val,
            case_type=case_type,
            case_number=case_number,
            email_id=email_id,
            priority=priority,
            stp_eligible=stp_eligible,
            confidence_score=confidence_score,
            source="case-retry",
            message_id=message_id,
        )

        return CaseRetryResponse(
            case_id=case_id_val,
            case_number=case_number,
            message_id=message_id,
            status="classified",
            previous_status=previous_status,
        )
