"""Intake classification — `17` §3.1."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.hermes import HermesClient, HermesError
from app.core.state_machine import CaseStateMachine
from app.models.case import Case, Counterparty
from app.models.mail import Email, EmailAttachment
from app.repositories.case import CaseRepository
from app.schemas.hermes import (
    AttachmentInput,
    ClassifyEmailRequest,
    CounterpartyHint,
)
from app.services.queue_router import enqueue_accounts, enqueue_dead_letter, schedule_retry

logger = logging.getLogger(__name__)

VALID_CASE_TYPES = [
    "ar_invoice",
    "ar_payment_advice",
    "ar_credit_note",
    "ap_invoice",
    "ap_po_validation",
    "ap_payment_proposal",
    "treasury_reconciliation",
    "treasury_fx",
    "treasury_suspense",
    "general_inquiry",
]

SLA_HOURS = {"critical": 1, "high": 4, "medium": 24, "low": 72}


def routing_decision(
    *, case_type: str, confidence: float, stp_from_hermes: bool
) -> tuple[str, str, bool, str]:
    """Returns (case_status, priority, stp_eligible, trigger)."""
    if case_type == "unknown" or confidence < 0.70:
        return "manual_review", "low", False, "classification_failed"
    stp = stp_from_hermes and confidence >= 0.90
    if confidence >= 0.90:
        return "classified", "high", stp, "ai_classified"
    if confidence >= 0.70:
        return "classified", "medium", False, "ai_classified"
    return "manual_review", "low", False, "classification_failed"


class ClassificationService:
    def __init__(
        self,
        session: AsyncSession,
        hermes: HermesClient | None = None,
    ) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._hermes = hermes or HermesClient()
        self._machine = CaseStateMachine()

    async def process_intake(self, raw: str) -> dict:
        payload = json.loads(raw)
        email_id = UUID(payload["email_id"])
        email = await self._cases.get_email(email_id)
        if email is None:
            return {"status": "skipped", "reason": "email_not_found"}
        if email.case_id:
            return {"status": "skipped", "reason": "already_linked", "case_id": str(email.case_id)}
        if email.status == "duplicate":
            return {"status": "skipped", "reason": "duplicate_email"}

        attachments = await self._load_attachments(email_id)
        counterparties = await self._load_counterparty_hints()

        classify_req = ClassifyEmailRequest(
            email_id=email_id,
            subject=email.subject,
            body_preview=(email.body_preview or "")[:500],
            from_address=email.from_address,
            mailbox=email.mailbox_address,
            attachments=attachments,
            known_counterparties=counterparties,
            valid_case_types=VALID_CASE_TYPES,
        )

        try:
            hermes_resp = await self._hermes.classify_email(classify_req)
        except HermesError as exc:
            return await self._handle_hermes_failure(email, payload, exc)

        output = hermes_resp.output
        if output is None:
            return await self._handle_hermes_failure(
                email, payload, HermesError("HERMES_PARSE_ERROR", "Empty classification output")
            )

        confidence = float(hermes_resp.confidence_score)
        case_type = output.case_type if output.case_type in VALID_CASE_TYPES else "general_inquiry"
        status, priority, stp_eligible, trigger = routing_decision(
            case_type=case_type,
            confidence=confidence,
            stp_from_hermes=output.stp_eligible,
        )

        counterparty = await self._resolve_counterparty(
            email=email,
            hermes_name=output.counterparty_match,
        )

        case_number = await self._cases.generate_case_number()
        now = datetime.now(UTC)
        case = Case(
            case_number=case_number,
            type=case_type,
            status="inbound",
            priority=priority,
            confidence_score=Decimal(str(round(confidence, 2))),
            stp_eligible=stp_eligible,
            subject=email.subject,
            description=email.body_preview,
            email_id=email.id,
            counterparty_id=counterparty.id if counterparty else None,
            counterparty_name=(
                output.counterparty_match or email.from_name or email.from_address
            ),
            classification_metadata={
                "ai_classified": True,
                "classified_as": case_type,
                "classification_confidence": confidence,
                "classified_at": now.isoformat(),
                "model_used": hermes_resp.model_used,
                "prompt_version": hermes_resp.prompt_version,
            },
            workflow_metadata={"current_stage": "classification", "worker": "accounts-worker"},
            sla_deadline=now + timedelta(hours=SLA_HOURS.get(priority, 24)),
            sla_status="on_track",
        )
        self._session.add(case)
        await self._session.flush()

        email.classified_as = case_type
        email.classification_confidence = Decimal(str(round(confidence, 2)))
        email.classified_at = now
        email.status = "classified"
        email.case_id = case.id
        email.case_number = case.case_number

        definition = await self._cases.ensure_workflow_definition(case_type)
        instance = await self._cases.create_workflow_instance(case, definition)

        result = self._machine.transition(case, trigger, context={"confidence": confidence})
        if not result.success:
            await enqueue_dead_letter(payload=payload, reason=result.guard_failed or "transition_failed")
            await self._session.flush()
            return {"status": "failed", "reason": result.guard_failed}

        await self._cases.record_transition(
            instance=instance,
            from_state=result.from_state.value,
            to_state=result.to_state.value,
            trigger=trigger,
            actor="accounts-worker",
        )
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="classification",
            from_status="inbound",
            to_status=case.status,
            actor="AI Classification Agent",
            description=f"AI classified as {case_type} (confidence: {confidence:.2f})",
            metadata={
                "confidence": confidence,
                "model_used": hermes_resp.model_used,
                "stp_eligible": stp_eligible,
                "reasoning": output.reasoning,
            },
        )

        if case.status == "classified":
            await enqueue_accounts(
                case_id=case.id,
                case_type=case.type,
                case_number=case.case_number,
                email_id=email.id,
                priority=case.priority,
                stp_eligible=case.stp_eligible,
                confidence_score=confidence,
            )
            return {"status": "routed", "case_id": str(case.id), "case_number": case.case_number}

        return {"status": "manual_review", "case_id": str(case.id), "case_number": case.case_number}

    async def _handle_hermes_failure(self, email: Email, payload: dict, exc: HermesError) -> dict:
        logger.warning("Hermes classification failed: %s", exc)
        email.status = "failed"
        await self._session.flush()
        retry_count = int(payload.get("retry_count", 0))
        if retry_count < 3:
            await schedule_retry(
                payload={"raw": json.dumps(payload), "retry_count": retry_count + 1},
                delay_seconds=60 * (2**retry_count),
            )
            return {"status": "retry_scheduled", "error": exc.error_code}
        await enqueue_dead_letter(payload=payload, reason=exc.error_code)
        return {"status": "failed", "error": exc.error_code}

    async def _load_attachments(self, email_id: UUID) -> list[AttachmentInput]:
        result = await self._session.execute(
            select(EmailAttachment).where(EmailAttachment.email_id == email_id)
        )
        return [
            AttachmentInput(
                attachment_id=row.id,
                filename=row.filename,
                mime_type=row.mime_type,
                extracted_text=row.extracted_text,
            )
            for row in result.scalars().all()
        ]

    async def _load_counterparty_hints(self, limit: int = 200) -> list[CounterpartyHint]:
        result = await self._session.execute(select(Counterparty).limit(limit))
        return [
            CounterpartyHint(
                name=row.name,
                code=row.code,
                type=row.type,
                is_recurring=row.is_recurring,
            )
            for row in result.scalars().all()
        ]

    async def _resolve_counterparty(
        self, *, email: Email, hermes_name: str | None
    ) -> Counterparty | None:
        candidates = [email.from_name, hermes_name]
        for name in candidates:
            if not name:
                continue
            result = await self._session.execute(
                select(Counterparty).where(Counterparty.name.ilike(name)).limit(1)
            )
            match = result.scalar_one_or_none()
            if match:
                return match

        cp = Counterparty(
            name=hermes_name or email.from_name or email.from_address,
            type="supplier",
            contact_email=email.from_address,
        )
        self._session.add(cp)
        await self._session.flush()
        return cp


class GeneralInquiryHandler:
    """`17` §3.3 — route general_inquiry to manual review."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)

    async def process(self, message: dict) -> dict:
        case_id = UUID(message["case_id"])
        case = await self._cases.get(case_id)
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}

        if case.type != "general_inquiry":
            return {"status": "skipped", "reason": "not_general_inquiry"}

        from_status = case.status
        case.status = "manual_review"
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "reason": "general_inquiry_requires_manual_handling",
        }
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="status_change",
            from_status=from_status,
            to_status="manual_review",
            actor="accounts-worker",
            description="General inquiry requires manual handling",
        )
        await self._session.flush()
        return {"status": "manual_review", "case_id": str(case.id)}
