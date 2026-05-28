"""Case lifecycle with state machine persistence — `08` §12.2."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.core.state_machine import CaseStateMachine, TransitionResult
from app.models.user import User
from app.policies.engine import PolicyEngine
from app.repositories.case import CaseRepository
from app.repositories.policy import PolicyRepository
from fastapi import status

from app.schemas.auth import TokenData
from app.schemas.case import CaseRetryResponse
from app.services.case_retry import execute_case_retry
from app.services.timeline_actor import timeline_actor_label_for_user
from app.services.wasabi_archive import WasabiArchiveService


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
            actor_label = "system"
            if user is not None:
                db_user = await self._session.get(User, user.user_id)
                actor_label = timeline_actor_label_for_user(
                    db_user, fallback=str(user.user_id)
                )
            await self._cases.record_transition(
                instance=instance,
                from_state=result.from_state.value,
                to_state=result.to_state.value,
                trigger=trigger,
                actor=actor_label,
                metadata={"policy_action": policy_action},
            )
            await self._cases.add_timeline(
                case_id=case.id,
                event_type="status_changed",
                from_status=result.from_state.value,
                to_status=result.to_state.value,
                actor=actor_label,
                description=f"Trigger: {trigger}",
                actor_user_id=user.user_id if user else None,
            )

        await self._session.commit()
        await self._session.refresh(case)
        return result

    async def retry_case(self, case_id: UUID, *, user: TokenData) -> CaseRetryResponse:
        """Delegate to module-level retry (no request-scoped session across Redis)."""
        return await execute_case_retry(case_id, user=user)
