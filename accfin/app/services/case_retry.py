"""Manual case retry — DB phase then Redis enqueue (no ORM across external awaits)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.exceptions import AppHTTPException
from app.models.accounting_period import AccountingPeriod
from app.models.case import Case
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.schemas.case import CaseRetryResponse
from app.services.queue_router import enqueue_accounts
from fastapi import status

RETRYABLE_STATUSES = frozenset({"exception", "manual_review"})
RETRYABLE_HERMES_ON_HOLD_CODES = frozenset({"HERMES_TIMEOUT", "HERMES_UNAVAILABLE"})


@dataclass(frozen=True)
class _CaseRetrySnapshot:
    case_id: UUID
    case_number: str
    case_type: str
    email_id: UUID | None
    priority: str
    stp_eligible: bool
    confidence_score: float
    message_id: str
    previous_status: str


async def _period_closed_hold_retryable(session: AsyncSession, case: Case) -> bool:
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
    period = await session.get(AccountingPeriod, pid)
    return period is not None and period.status != "closed"


def _transient_hermes_code(meta: dict) -> str | None:
    for key in ("error_code", "error_type", "reason_code"):
        code = str(meta.get(key) or "").strip().upper()
        if code in RETRYABLE_HERMES_ON_HOLD_CODES:
            return code
    return None


def _transient_hermes_hold_retryable(case: Case) -> bool:
    if case.status != "on_hold":
        return False
    return _transient_hermes_code(case.workflow_metadata or {}) is not None


async def _persist_case_retry(case_id: UUID, user: TokenData) -> _CaseRetrySnapshot:
    """All DB writes in one session; commit before returning (no Redis in this phase)."""
    message_id = str(uuid4())
    factory = get_session_factory()

    async with factory() as session:
        cases = CaseRepository(session)
        case = await cases.get_for_retry(case_id)
        if case is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found"
            )

        retryable = case.status in RETRYABLE_STATUSES
        if not retryable:
            retryable = await _period_closed_hold_retryable(session, case)
        if not retryable:
            retryable = _transient_hermes_hold_retryable(case)
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
        meta = dict(case.workflow_metadata or {})
        for key in (
            "error_code",
            "error_message",
            "error_reason",
            "error_type",
            "reason_code",
            "reason",
        ):
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
            case_id=case.id,
            event_type="case_retry",
            from_status=previous_status,
            to_status="classified",
            actor=str(user.user_id),
            description="Manual retry — requeued to accounts_queue",
            metadata={"queue_message_id": message_id},
            actor_user_id=user.user_id,
        )
        await session.commit()

        return _CaseRetrySnapshot(
            case_id=case.id,
            case_number=case.case_number,
            case_type=case.type,
            email_id=case.email_id,
            priority=case.priority or "medium",
            stp_eligible=bool(case.stp_eligible),
            confidence_score=float(case.confidence_score or 0),
            message_id=message_id,
            previous_status=previous_status,
        )


async def execute_case_retry(case_id: UUID, *, user: TokenData) -> CaseRetryResponse:
    """
    Requeue a case for worker processing.

    Phase 1: persist case + timeline (dedicated session, commit).
    Phase 2: enqueue to Redis (primitives only — no ORM).
    """
    snap = await _persist_case_retry(case_id, user)

    await enqueue_accounts(
        case_id=snap.case_id,
        case_type=snap.case_type,
        case_number=snap.case_number,
        email_id=snap.email_id,
        priority=snap.priority,
        stp_eligible=snap.stp_eligible,
        confidence_score=snap.confidence_score,
        source="case-retry",
        message_id=snap.message_id,
    )

    return CaseRetryResponse(
        case_id=snap.case_id,
        case_number=snap.case_number,
        message_id=snap.message_id,
        status="classified",
        previous_status=snap.previous_status,
    )
