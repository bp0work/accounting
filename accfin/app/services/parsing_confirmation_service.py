"""Finance UI parsing confirmation — confirm or reject before step 2B."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.exceptions import AppHTTPException
from app.models.case import Case
from app.models.mail import Email
from app.models.user import User
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.schemas.parsing_confirmation import (
    ConfirmParsingRequest,
    ConfirmParsingResponse,
    RejectParsingRequest,
    RejectParsingResponse,
)
from app.services.executive_mail_service import ExecutiveMailService
from app.services.queue_router import enqueue_accounts
from app.services.timeline_actor import timeline_actor_label_for_user
from fastapi import status
from workers.common.parsing_confirmation import normalize_extracted_fields

CONFIRM_PARSING_ROLES = frozenset(
    {"accounts_clerk", "finance_manager", "cfo", "finance_director"}
)


def _assert_confirm_role(user: TokenData) -> None:
    role = (user.role or "").lower()
    if role in CONFIRM_PARSING_ROLES or "tenant:admin" in user.permissions:
        return
    raise AppHTTPException(
        status.HTTP_403_FORBIDDEN,
        "INSUFFICIENT_PERMISSION",
        "accounts_clerk, finance_manager, cfo, or finance_director role required",
    )


def _count_corrections(before: dict, after: dict) -> int:
    n = 0
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        if str(before.get(key) or "") != str(after.get(key) or ""):
            n += 1
    return n


async def execute_confirm_parsing(
    case_id: UUID,
    *,
    user: TokenData,
    body: ConfirmParsingRequest,
) -> ConfirmParsingResponse:
    _assert_confirm_role(user)
    message_id = str(uuid4())
    confirmed_at = datetime.now(UTC)
    fields_in = body.extracted_fields.model_dump(mode="json")
    normalized_new = normalize_extracted_fields(fields_in)

    factory = get_session_factory()
    async with factory() as session:
        cases = CaseRepository(session)
        case = await cases.get(case_id)
        if case is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found"
            )
        if case.status != "pending_confirmation":
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_STATUS",
                f"Case must be pending_confirmation (current: {case.status})",
            )

        meta = dict(case.workflow_metadata or {})
        before = dict(meta.get("extracted_fields") or {})
        corrections = _count_corrections(before, normalized_new)
        meta["extracted_fields"] = normalized_new
        meta["parsing_confirmed_by"] = str(user.user_id)
        meta["parsing_confirmed_at"] = confirmed_at.isoformat()
        meta.pop("pending_parsing_confirmation", None)
        meta["current_stage"] = "processing"
        case.workflow_metadata = meta
        previous_status = case.status
        case.status = "classified"

        db_user = await session.get(User, user.user_id)
        actor_label = timeline_actor_label_for_user(
            db_user, fallback=str(user.user_id)
        )
        await cases.add_timeline(
            case_id=case.id,
            event_type="parsing_confirmed",
            from_status=previous_status,
            to_status="classified",
            actor=actor_label,
            description=f"Parsing confirmed by {actor_label} with {corrections} correction(s)",
            metadata={
                "correction_count": corrections,
                "queue_message_id": message_id,
            },
            actor_user_id=user.user_id,
        )
        await session.commit()

        snap = _case_enqueue_snapshot(case, message_id)

    await enqueue_accounts(
        case_id=snap.case_id,
        case_type=snap.case_type,
        case_number=snap.case_number,
        email_id=snap.email_id,
        priority=snap.priority,
        stp_eligible=snap.stp_eligible,
        confidence_score=snap.confidence_score,
        source="parsing-confirmation",
        message_id=message_id,
        parsing_confirmed=True,
    )

    return ConfirmParsingResponse(
        case_id=snap.case_id,
        case_number=snap.case_number,
        status="classified",
        message_id=message_id,
        parsing_confirmed_by=user.user_id,
        parsing_confirmed_at=confirmed_at,
        correction_count=corrections,
    )


async def execute_reject_parsing(
    case_id: UUID,
    *,
    user: TokenData,
    body: RejectParsingRequest,
) -> RejectParsingResponse:
    _assert_confirm_role(user)

    factory = get_session_factory()
    async with factory() as session:
        cases = CaseRepository(session)
        case = await cases.get(case_id)
        if case is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found"
            )
        if case.status != "pending_confirmation":
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_STATUS",
                f"Case must be pending_confirmation (current: {case.status})",
            )

        email: Email | None = None
        if case.email_id:
            email = await cases.get_email(case.email_id)

        previous_status = case.status
        case.status = "case_rejected"
        meta = dict(case.workflow_metadata or {})
        meta["manager_decision"] = "rejected"
        meta["rejection_reason"] = body.reason
        case.workflow_metadata = meta

        db_user = await session.get(User, user.user_id)
        actor_label = timeline_actor_label_for_user(
            db_user, fallback=str(user.user_id)
        )
        await cases.add_timeline(
            case_id=case.id,
            event_type="parsing_rejected",
            from_status=previous_status,
            to_status="case_rejected",
            actor=actor_label,
            description=f"Parsing rejected by {actor_label}",
            metadata={"reason": body.reason},
            actor_user_id=user.user_id,
        )

        if email is not None:
            svc = ExecutiveMailService(session)
            await svc.queue_submitter_rejection(
                case=case,
                email=email,
                reason=body.reason,
                manager_comment=None,
            )

        case_number = case.case_number
        await session.commit()

    return RejectParsingResponse(
        case_id=case_id,
        case_number=case_number,
        status="case_rejected",
    )


class _EnqueueSnapshot:
    __slots__ = (
        "case_id",
        "case_type",
        "case_number",
        "email_id",
        "priority",
        "stp_eligible",
        "confidence_score",
    )

    def __init__(self, case: Case, message_id: str) -> None:
        self.case_id = case.id
        self.case_type = case.type
        self.case_number = case.case_number
        self.email_id = case.email_id
        self.priority = case.priority or "medium"
        self.stp_eligible = bool(case.stp_eligible)
        meta = case.workflow_metadata or {}
        self.confidence_score = float(
            meta.get("extraction_confidence") or case.confidence_score or 0
        )


def _case_enqueue_snapshot(case: Case, message_id: str) -> _EnqueueSnapshot:
    return _EnqueueSnapshot(case, message_id)
