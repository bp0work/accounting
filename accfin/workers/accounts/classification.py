"""Intake classification — `17` §3.1."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient, HermesError
from app.core.database import get_session_factory
from app.core.state_machine import CaseStateMachine
from app.models.case import Case, Counterparty
from app.models.mail import Email, EmailAttachment
from app.repositories.case import CaseRepository
from app.schemas.hermes import (
    AttachmentInput,
    ClassifyEmailRequest,
    ClassifyEmailResponse,
    CounterpartyHint,
)
from app.services.case_service import CaseService
from app.services.email_context import ensure_attachment_texts
from app.services.executive_mail_service import ExecutiveMailService
from app.services.queue_router import enqueue_dead_letter, route_case_to_queue, schedule_retry

logger = logging.getLogger(__name__)

VALID_CASE_TYPES = [
    "ar_invoice",
    "ar_payment_advice",
    "ar_credit_note",
    "ap_invoice",
    "ap_po_validation",
    "ap_payment_proposal",
    "expense_claim",
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


@dataclass(frozen=True)
class EmailSnapshot:
    """Plain intake email fields — safe across Hermes HTTP / thread handoffs."""

    id: UUID
    subject: str
    body_preview: str | None
    from_address: str
    from_name: str | None
    mailbox_address: str
    received_at: datetime | None
    case_id: UUID | None
    status: str


@dataclass(frozen=True)
class IntakePrepareResult:
    snapshot: EmailSnapshot
    classify_req: ClassifyEmailRequest


def _email_snapshot(email: Email) -> EmailSnapshot:
    """Read ORM scalars in the async greenlet before any external await."""
    return EmailSnapshot(
        id=email.id,
        subject=email.subject,
        body_preview=email.body_preview,
        from_address=email.from_address,
        from_name=email.from_name,
        mailbox_address=email.mailbox_address,
        received_at=email.received_at,
        case_id=email.case_id,
        status=email.status,
    )


async def _load_attachments(session: AsyncSession, email_id: UUID) -> list[AttachmentInput]:
    result = await session.execute(
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


async def _load_counterparty_hints(session: AsyncSession, limit: int = 200) -> list[CounterpartyHint]:
    result = await session.execute(select(Counterparty).limit(limit))
    return [
        CounterpartyHint(
            name=row.name,
            code=row.code,
            type=row.type,
            is_recurring=row.is_recurring,
        )
        for row in result.scalars().all()
    ]


async def _prepare_intake(
    session: AsyncSession,
    email_id: UUID,
    payload: dict,
    hermes: HermesClient,
) -> IntakePrepareResult | dict:
    cases = CaseRepository(session)
    email = await cases.get_email(email_id)
    if email is None:
        return {"status": "skipped", "reason": "email_not_found"}
    if email.case_id:
        return {"status": "skipped", "reason": "already_linked", "case_id": str(email.case_id)}
    if email.status == "duplicate":
        return {"status": "skipped", "reason": "duplicate_email"}

    snapshot = _email_snapshot(email)

    await ensure_attachment_texts(session, email_id, hermes=hermes)

    classify_req = ClassifyEmailRequest(
        email_id=email_id,
        subject=snapshot.subject,
        body_preview=(snapshot.body_preview or "")[:500],
        from_address=snapshot.from_address,
        mailbox=snapshot.mailbox_address,
        attachments=await _load_attachments(session, email_id),
        known_counterparties=await _load_counterparty_hints(session),
        valid_case_types=VALID_CASE_TYPES,
    )
    return IntakePrepareResult(snapshot=snapshot, classify_req=classify_req)


async def _resolve_counterparty(
    session: AsyncSession,
    *,
    snapshot: EmailSnapshot,
    hermes_name: str | None,
) -> Counterparty | None:
    candidates = [snapshot.from_name, hermes_name]
    for name in candidates:
        if not name:
            continue
        result = await session.execute(
            select(Counterparty).where(Counterparty.name.ilike(name)).limit(1)
        )
        match = result.scalar_one_or_none()
        if match:
            return match

    cp = Counterparty(
        name=hermes_name or snapshot.from_name or snapshot.from_address,
        type="supplier",
        contact_email=snapshot.from_address,
    )
    session.add(cp)
    await session.flush()
    return cp


async def _get_email_for_update(session: AsyncSession, email_id: UUID) -> Email | None:
    cases = CaseRepository(session)
    return await cases.get_email(email_id)


async def _apply_successful_classification(
    session: AsyncSession,
    *,
    snapshot: EmailSnapshot,
    hermes_resp: ClassifyEmailResponse,
    payload: dict,
    defer_queue_route: bool = False,
) -> dict:
    cases = CaseRepository(session)
    executive_mail = ExecutiveMailService(session)
    case_service = CaseService(session)
    machine = CaseStateMachine()

    email = await _get_email_for_update(session, snapshot.id)
    if email is None:
        return {"status": "skipped", "reason": "email_not_found"}

    output = hermes_resp.output
    assert output is not None

    confidence = float(hermes_resp.confidence_score)
    case_type = output.case_type if output.case_type in VALID_CASE_TYPES else "general_inquiry"
    status, priority, stp_eligible, trigger = routing_decision(
        case_type=case_type,
        confidence=confidence,
        stp_from_hermes=output.stp_eligible,
    )

    counterparty = await _resolve_counterparty(
        session,
        snapshot=snapshot,
        hermes_name=output.counterparty_match,
    )

    case_number = await cases.generate_case_number()
    now = datetime.now(UTC)
    case = Case(
        case_number=case_number,
        type=case_type,
        status="inbound",
        priority=priority,
        confidence_score=Decimal(str(round(confidence, 2))),
        stp_eligible=stp_eligible,
        subject=snapshot.subject,
        description=snapshot.body_preview,
        email_id=snapshot.id,
        counterparty_id=counterparty.id if counterparty else None,
        counterparty_name=(
            output.counterparty_match or snapshot.from_name or snapshot.from_address
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
    session.add(case)
    await session.flush()

    email.classified_as = case_type
    email.classification_confidence = Decimal(str(round(confidence, 2)))
    email.classified_at = now
    email.status = "classified"
    email.case_id = case.id
    email.case_number = case.case_number
    await case_service.on_case_linked_to_email(case, snapshot.id)

    definition = await cases.ensure_workflow_definition(case_type)
    instance = await cases.create_workflow_instance(case, definition)

    result = machine.transition(case, trigger, context={"confidence": confidence})
    if not result.success:
        await enqueue_dead_letter(payload=payload, reason=result.guard_failed or "transition_failed")
        await session.flush()
        return {"status": "failed", "reason": result.guard_failed}

    await cases.record_transition(
        instance=instance,
        from_state=result.from_state.value,
        to_state=result.to_state.value,
        trigger=trigger,
        actor="accounts-worker",
    )
    await cases.add_timeline(
        case_id=case.id,
        event_type="created",
        from_status=None,
        to_status="inbound",
        actor="mail-gateway",
        description=f"Email received from {snapshot.from_address}",
        metadata={
            "from_address": snapshot.from_address,
            "from_name": snapshot.from_name,
            "subject": snapshot.subject,
            "received_at": snapshot.received_at.isoformat() if snapshot.received_at else None,
            "mailbox": snapshot.mailbox_address,
        },
    )
    await cases.add_timeline(
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
        await executive_mail.log_step(
            action="classified",
            summary=f"[{case.case_number}] Classified as {case_type} (confidence {confidence:.2f})",
            actor_name="accounts-worker",
            case_id=case.id,
            email_id=snapshot.id,
        )
        await executive_mail.queue_acknowledgement(case=case, email=email)
        result: dict = {
            "status": "routed",
            "case_id": str(case.id),
            "case_number": case.case_number,
        }
        if defer_queue_route:
            result["_defer_queue_route"] = {
                "case_id": str(case.id),
                "email_id": str(snapshot.id),
                "confidence_score": confidence,
            }
        else:
            message_id = await route_case_to_queue(
                case=case,
                session=session,
                email_id=snapshot.id,
                confidence_score=confidence,
            )
            result["queue_message_id"] = message_id
        return result

    await executive_mail.log_step(
        action="classified",
        summary=f"[{case.case_number}] Classified as {case_type} — manual review required",
        actor_name="accounts-worker",
        case_id=case.id,
        email_id=snapshot.id,
    )
    await executive_mail.queue_acknowledgement(case=case, email=email)
    await executive_mail.escalate_to_manager(
        case=case,
        email=email,
        reason_code="classification_failed",
        summary="Classification requires manager review",
        error_detail=f"Low confidence ({confidence:.2f}) or case type {case_type}",
        actor_name="accounts-worker",
    )
    return {"status": "manual_review", "case_id": str(case.id), "case_number": case.case_number}


async def _handle_hermes_failure(
    session: AsyncSession,
    *,
    snapshot: EmailSnapshot,
    payload: dict,
    exc: HermesError,
) -> dict:
    logger.warning("Hermes classification failed: %s", exc)
    cases = CaseRepository(session)
    executive_mail = ExecutiveMailService(session)
    case_service = CaseService(session)

    email = await _get_email_for_update(session, snapshot.id)
    if email is None:
        return {"status": "skipped", "reason": "email_not_found"}

    retry_count = int(payload.get("retry_count", 0))
    if retry_count < 3:
        email.status = "queued"
        await session.flush()
        await schedule_retry(
            payload={"raw": json.dumps(payload), "retry_count": retry_count + 1},
            delay_seconds=60 * (2**retry_count),
        )
        return {"status": "retry_scheduled", "error": exc.error_code}

    case_number = await cases.generate_case_number()
    now = datetime.now(UTC)
    case = Case(
        case_number=case_number,
        type="general_inquiry",
        status="on_hold",
        priority="medium",
        subject=snapshot.subject,
        description=snapshot.body_preview,
        email_id=snapshot.id,
        classification_metadata={
            "source": "intake",
            "classification_failed": True,
            "error_code": exc.error_code,
        },
        workflow_metadata={"current_stage": "classification", "worker": "accounts-worker"},
        sla_deadline=now + timedelta(hours=24),
        sla_status="on_track",
    )
    session.add(case)
    await session.flush()

    email.status = "failed"
    email.case_id = case.id
    email.case_number = case.case_number
    await session.flush()
    await case_service.on_case_linked_to_email(case, snapshot.id)

    await cases.add_timeline(
        case_id=case.id,
        event_type="created",
        from_status=None,
        to_status="on_hold",
        actor="mail-gateway",
        description=f"Email received from {snapshot.from_address}",
        metadata={
            "from_address": snapshot.from_address,
            "from_name": snapshot.from_name,
            "subject": snapshot.subject,
            "received_at": snapshot.received_at.isoformat() if snapshot.received_at else None,
            "mailbox": snapshot.mailbox_address,
        },
    )

    await executive_mail.log_step(
        action="email_received",
        summary=f"[{case.case_number}] Intake failed classification after retries",
        actor_name="accounts-worker",
        case_id=case.id,
        email_id=snapshot.id,
        metadata={"error_code": exc.error_code},
    )
    await executive_mail.queue_acknowledgement(case=case, email=email)
    await executive_mail.escalate_to_manager(
        case=case,
        email=email,
        reason_code=exc.error_code,
        summary="Email classification failed",
        error_detail=str(exc),
        actor_name="accounts-worker",
    )

    await enqueue_dead_letter(payload=payload, reason=exc.error_code)
    return {
        "status": "escalated_to_manager",
        "error": exc.error_code,
        "case_id": str(case.id),
        "case_number": case.case_number,
    }


async def process_intake_message(raw: str, *, hermes: HermesClient | None = None) -> dict:
    """
    Production intake path: separate DB sessions around Hermes HTTP (no ORM across awaits).
    Mirrors `gateway/imap/poller.py` — `async with session_factory() as session` per phase.
    """
    client = hermes or HermesClient()
    payload = json.loads(raw)
    email_id = UUID(payload["email_id"])
    factory = get_session_factory()

    async with factory() as session:
        prep = await _prepare_intake(session, email_id, payload, client)
        if isinstance(prep, dict):
            return prep
        await session.commit()

    try:
        hermes_resp = await client.classify_email(prep.classify_req)
    except HermesError as exc:
        async with factory() as session:
            result = await _handle_hermes_failure(
                session, snapshot=prep.snapshot, payload=payload, exc=exc
            )
            await session.commit()
            return result

    if hermes_resp.output is None:
        async with factory() as session:
            result = await _handle_hermes_failure(
                session,
                snapshot=prep.snapshot,
                payload=payload,
                exc=HermesError("HERMES_PARSE_ERROR", "Empty classification output"),
            )
            await session.commit()
            return result

    async with factory() as session:
        result = await _apply_successful_classification(
            session,
            snapshot=prep.snapshot,
            hermes_resp=hermes_resp,
            payload=payload,
            defer_queue_route=True,
        )
        defer = result.pop("_defer_queue_route", None)
        await session.commit()
        if defer is not None:
            case = await session.get(Case, UUID(defer["case_id"]))
            if case is not None:
                message_id = await route_case_to_queue(
                    case=case,
                    session=session,
                    email_id=UUID(defer["email_id"]),
                    confidence_score=defer["confidence_score"],
                )
                result["queue_message_id"] = message_id
        return result


class ClassificationService:
    """Backward-compatible wrapper; production uses `process_intake_message`."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        hermes: HermesClient | None = None,
    ) -> None:
        self._session = session
        self._hermes = hermes or HermesClient()

    async def process_intake(self, raw: str) -> dict:
        if self._session is not None:
            return await self._process_intake_injected_session(raw)
        return await process_intake_message(raw, hermes=self._hermes)

    async def _process_intake_injected_session(self, raw: str) -> dict:
        """Integration tests: one session, snapshot before Hermes await."""
        payload = json.loads(raw)
        email_id = UUID(payload["email_id"])
        prep = await _prepare_intake(self._session, email_id, payload, self._hermes)
        if isinstance(prep, dict):
            return prep

        try:
            hermes_resp = await self._hermes.classify_email(prep.classify_req)
        except HermesError as exc:
            return await _handle_hermes_failure(
                self._session, snapshot=prep.snapshot, payload=payload, exc=exc
            )

        if hermes_resp.output is None:
            return await _handle_hermes_failure(
                self._session,
                snapshot=prep.snapshot,
                payload=payload,
                exc=HermesError("HERMES_PARSE_ERROR", "Empty classification output"),
            )

        return await _apply_successful_classification(
            self._session,
            snapshot=prep.snapshot,
            hermes_resp=hermes_resp,
            payload=payload,
        )


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
