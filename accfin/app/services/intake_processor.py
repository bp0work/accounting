"""Consume intake_queue → create case → classify → route to accounts_queue."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.state_machine import CaseStateMachine
from app.repositories.case import CaseRepository
from app.services.queue_router import enqueue_accounts, enqueue_dead_letter, schedule_retry

logger = logging.getLogger("orchestrator.intake")

DEFAULT_CASE_TYPE = "general_inquiry"
CLASSIFICATION_CONFIDENCE_DEFAULT = 0.75


class IntakeProcessor:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._machine = CaseStateMachine()

    async def process_message(self, raw: str) -> dict:
        payload = json.loads(raw)
        email_id = UUID(payload["email_id"])
        email = await self._cases.get_email(email_id)
        if email is None:
            return {"status": "skipped", "reason": "email_not_found"}

        if email.case_id:
            return {"status": "skipped", "reason": "already_linked", "case_id": str(email.case_id)}

        if email.status == "duplicate":
            return {"status": "skipped", "reason": "duplicate_email"}

        case_type = email.classified_as or DEFAULT_CASE_TYPE
        confidence = float(email.classification_confidence or CLASSIFICATION_CONFIDENCE_DEFAULT)

        case = await self._cases.create_case_from_email(
            email=email,
            case_type=case_type,
            confidence=confidence,
        )
        definition = await self._cases.ensure_workflow_definition(case_type)
        instance = await self._cases.create_workflow_instance(case, definition)

        trigger = "ai_classified" if confidence >= 0.70 else "classification_failed"
        result = self._machine.transition(
            case,
            trigger,
            context={"confidence": confidence},
        )
        if not result.success:
            await enqueue_dead_letter(payload=payload, reason=result.guard_failed or "transition_failed")
            await self._session.commit()
            return {"status": "failed", "reason": result.guard_failed}

        await self._cases.record_transition(
            instance=instance,
            from_state=result.from_state.value,
            to_state=result.to_state.value,
            trigger=trigger,
            actor="orchestrator",
        )
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="case_created",
            from_status=None,
            to_status=result.to_state.value,
            actor="orchestrator",
            description=f"Created from email {email_id}",
            metadata={"mailbox": payload.get("mailbox")},
        )

        if result.to_state and result.to_state.value == "classified":
            start = self._machine.transition(case, "processing_started", context={})
            if start.success and start.to_state:
                await self._cases.record_transition(
                    instance=instance,
                    from_state=start.from_state.value,
                    to_state=start.to_state.value,
                    trigger="processing_started",
                    actor="orchestrator",
                )

        await self._session.commit()

        if case.status in ("classified", "processing"):
            await enqueue_accounts(
                case_id=case.id,
                case_type=case.type,
                case_number=case.case_number,
            )
            return {"status": "routed", "case_id": str(case.id), "case_number": case.case_number}

        return {"status": "created", "case_id": str(case.id), "case_number": case.case_number}

    async def handle_failure(self, raw: str, error: str, retry_count: int) -> None:
        payload = json.loads(raw)
        max_retries = 3
        if retry_count < max_retries:
            delay = min(300, 30 * (2**retry_count))
            await schedule_retry(payload={"raw": raw, "retry_count": retry_count + 1}, delay_seconds=delay)
        else:
            await enqueue_dead_letter(payload=payload, reason=error)
