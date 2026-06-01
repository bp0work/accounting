"""Case and workflow API — Phase 4; finance oversight dashboard."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.dependencies import require_manual_review_escalation, require_permission
from app.core.exceptions import AppHTTPException
from app.core.redis_client import get_redis
from app.models.accounting_period import AccountingPeriod
from app.models.mail import Email
from app.models.user import User
from app.models.policy import Approval
from app.repositories.case import CaseRepository
from app.repositories.policy import PolicyRepository
from app.schemas.auth import TokenData
from app.schemas.case_attachment import CaseAttachmentListResponse
from app.schemas.case import (
    CaseDashboardResponse,
    CaseListResponse,
    CaseResponse,
    CaseRetryResponse,
    CaseStatusTransitionRequest,
    CaseStatusTransitionResponse,
    QueueStatusResponse,
    TimelineEntryResponse,
)
from app.schemas.executive_mail import (
    CaseEscalationRespondRequest,
    EscalationRespondResult,
)
from app.schemas.parsing_confirmation import (
    ConfirmParsingRequest,
    ConfirmParsingResponse,
    RejectParsingRequest,
    RejectParsingResponse,
)
from app.services.parsing_confirmation_service import (
    execute_confirm_parsing,
    execute_reject_parsing,
)
from app.services.case_attachments import CaseAttachmentService
from app.services.case_export import build_cases_csv
from app.services.case_metrics import is_case_overdue, processing_time_minutes
from app.services.case_journal_approval import build_journal_entry_approval_detail
from app.services.case_retry import execute_case_retry
from app.services.escalation_service import EscalationService
from app.services.case_service import CaseService
from app.services.timeline_actor import resolve_timeline_actor_display
from app.services.case_visibility import (
    case_action_by,
    case_status_group,
    case_status_group_label,
    case_status_label,
    case_submitted_by,
    client_vendor_name,
    error_reason,
    last_activity_at,
    processing_stage,
    status_reason,
)
from fastapi import status

router = APIRouter(tags=["Cases"])


async def _load_assignees_map(session: AsyncSession, cases: list) -> dict[UUID, User]:
    user_ids = {c.assigned_to for c in cases if c.assigned_to}
    if not user_ids:
        return {}
    result = await session.execute(
        select(User).where(User.id.in_(user_ids)).options(selectinload(User.role))
    )
    return {row.id: row for row in result.scalars().all()}


async def _load_email_senders_map(
    session: AsyncSession, cases: list
) -> dict[UUID, tuple[str | None, str | None]]:
    email_ids = {c.email_id for c in cases if c.email_id}
    if not email_ids:
        return {}
    result = await session.execute(
        select(Email.id, Email.from_name, Email.from_address).where(
            Email.id.in_(email_ids)
        )
    )
    return {row[0]: (row[1], row[2]) for row in result.all()}


async def _load_email_sender(
    session: AsyncSession, case
) -> tuple[str | None, str | None]:
    if case.email_id:
        result = await session.execute(
            select(Email.from_name, Email.from_address).where(Email.id == case.email_id)
        )
        row = result.one_or_none()
        if row:
            return row[0], row[1]
    meta = case.classification_metadata or {}
    from_name = meta.get("from_name")
    from_address = meta.get("from_address")
    return (
        str(from_name) if from_name else None,
        str(from_address) if from_address else None,
    )


async def _linked_gl_period_status(session: AsyncSession, case) -> str | None:
    meta = case.workflow_metadata or {}
    period_id = meta.get("gl_period_id")
    if not period_id:
        return None
    try:
        pid = UUID(str(period_id))
    except (TypeError, ValueError):
        return None
    period = await session.get(AccountingPeriod, pid)
    return period.status if period else None


async def _pending_approval_id(session: AsyncSession, case_id: UUID) -> UUID | None:
    result = await session.execute(
        select(Approval.id)
        .where(Approval.case_id == case_id, Approval.status == "pending")
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _case_response(
    session: AsyncSession,
    case,
    *,
    from_name: str | None = None,
    from_address: str | None = None,
    linked_gl_period_status: str | None = None,
    pending_approval_id: UUID | None = None,
    assignee: User | None = None,
    include_journal_entry: bool = False,
) -> CaseResponse:
    base = CaseResponse.model_validate(case)
    if from_address is None:
        meta = case.classification_metadata or {}
        fallback = meta.get("from_address")
        from_address = str(fallback) if fallback else None
    if from_name is None:
        meta = case.classification_metadata or {}
        fallback = meta.get("from_name")
        from_name = str(fallback) if fallback else None
    wf = case.workflow_metadata or {}
    journal_entry = (
        await build_journal_entry_approval_detail(session, case)
        if include_journal_entry
        else None
    )
    return base.model_copy(
        update={
            "from_address": from_address,
            "submitted_by": case_submitted_by(
                case, from_name=from_name, from_address=from_address
            ),
            "client_vendor_name": client_vendor_name(case),
            "completed_at": case.completed_at,
            "sla_deadline": case.sla_deadline,
            "processing_time_minutes": processing_time_minutes(case),
            "is_overdue": is_case_overdue(case),
            "processing_stage": processing_stage(case),
            "status_group": case_status_group(case),
            "status_group_label": case_status_group_label(case),
            "action_by": case_action_by(case, assignee),
            "status_label": case_status_label(case),
            "error_reason": error_reason(case),
            "status_reason": status_reason(case),
            "last_activity_at": last_activity_at(case),
            "workflow_metadata": wf,
            "classification_metadata": case.classification_metadata or {},
            "linked_gl_period_status": linked_gl_period_status,
            "current_approval_tier": case.current_approval_tier,
            "pending_approval_id": pending_approval_id,
            "binding_escalated_to_cfo": bool(wf.get("binding_escalated_to_cfo")),
            "journal_entry": journal_entry,
        }
    )


async def _queue_status() -> QueueStatusResponse:
    settings = get_settings()
    redis = get_redis()
    retry_count = await redis.zcard(settings.retry_queue_name)
    return QueueStatusResponse(
        intake_queue=await redis.llen(settings.intake_queue_name),
        accounts_queue=await redis.llen(settings.accounts_queue_name),
        dead_letter_queue=await redis.llen(settings.dead_letter_queue_name),
        retry_queue_pending=retry_count,
    )


@router.get("/cases/export")
async def export_cases_csv(
    date_from: date = Query(..., description="Start date (ISO), inclusive"),
    date_to: date = Query(..., description="End date (ISO), inclusive"),
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    if date_from > date_to:
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_DATE_RANGE",
            "date_from must be on or before date_to",
        )
    csv_text = await build_cases_csv(session, date_from=date_from, date_to=date_to)
    filename = f"transactions_{date_from.isoformat()}_{date_to.isoformat()}.csv"
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cases/dashboard", response_model=CaseDashboardResponse)
async def case_dashboard(
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseDashboardResponse:
    repo = CaseRepository(session)
    overdue = await repo.list_overdue_cases(limit=20)
    sender_map = await _load_email_senders_map(session, overdue)
    assignee_map = await _load_assignees_map(session, overdue)
    return CaseDashboardResponse(
        queue_depths=await _queue_status(),
        cases_by_status=await repo.count_by_status(),
        average_processing_time_minutes=await repo.average_processing_minutes_completed(),
        overdue_count=len(overdue),
        overdue_cases=[
            await _case_response(
                session,
                c,
                from_name=(sender_map.get(c.email_id) or (None, None))[0],
                from_address=(sender_map.get(c.email_id) or (None, None))[1],
                assignee=assignee_map.get(c.assigned_to) if c.assigned_to else None,
            )
            for c in overdue
        ],
    )


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseListResponse:
    service = CaseService(session)
    cases = await service.list_cases(
        limit=limit, status_filter=status, date_from=date_from, date_to=date_to
    )
    sender_map = await _load_email_senders_map(session, cases)
    assignee_map = await _load_assignees_map(session, cases)
    rows: list[CaseResponse] = []
    for c in cases:
        rows.append(
            await _case_response(
                session,
                c,
                from_name=(sender_map.get(c.email_id) or (None, None))[0],
                from_address=(sender_map.get(c.email_id) or (None, None))[1],
                assignee=assignee_map.get(c.assigned_to) if c.assigned_to else None,
            )
        )
    return CaseListResponse(data=rows)


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseResponse:
    service = CaseService(session)
    case = await service.get_case(case_id)
    from_name, from_address = await _load_email_sender(session, case)
    pending_id = await _pending_approval_id(session, case_id)
    linked_gl = await _linked_gl_period_status(session, case)
    assignee = None
    if case.assigned_to:
        result = await session.execute(
            select(User)
            .where(User.id == case.assigned_to)
            .options(selectinload(User.role))
        )
        assignee = result.scalar_one_or_none()
    return await _case_response(
        session,
        case,
        from_name=from_name,
        from_address=from_address,
        linked_gl_period_status=linked_gl,
        pending_approval_id=pending_id,
        assignee=assignee,
        include_journal_entry=True,
    )


@router.get("/cases/{case_id}/attachments", response_model=CaseAttachmentListResponse)
async def list_case_attachments(
    case_id: UUID,
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseAttachmentListResponse:
    service = CaseAttachmentService(session)
    items = await service.list_for_case(case_id)
    return CaseAttachmentListResponse(data=items)


@router.post("/cases/{case_id}/status", response_model=CaseStatusTransitionResponse)
async def transition_case_status(
    case_id: UUID,
    body: CaseStatusTransitionRequest,
    user: TokenData = Depends(require_permission("cases:write")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseStatusTransitionResponse:
    service = CaseService(session)
    result = await service.transition_case(
        case_id, body.trigger, user=user, context=body.context
    )
    return CaseStatusTransitionResponse(
        success=result.success,
        from_status=result.from_state.value,
        to_status=result.to_state.value if result.to_state else None,
        trigger=body.trigger,
        guard_failed=result.guard_failed,
    )


@router.post("/cases/{case_id}/escalation-respond", response_model=EscalationRespondResult)
async def case_escalation_respond(
    case_id: UUID,
    body: CaseEscalationRespondRequest,
    user: TokenData = Depends(require_manual_review_escalation()),
    session: AsyncSession = Depends(get_db_session),
) -> EscalationRespondResult:
    users = await session.execute(select(User).where(User.id == user.user_id))
    db_user = users.scalar_one_or_none()
    responder = db_user.email if db_user else f"user:{user.user_id}"

    service = EscalationService(session)
    return await service.respond_for_case(
        case_id,
        action=body.action,
        comment=body.comment,
        responder_email=responder,
    )


@router.post("/cases/{case_id}/retry", response_model=CaseRetryResponse)
async def retry_case(
    case_id: UUID,
    user: TokenData = Depends(require_permission("cases:write")),
) -> CaseRetryResponse:
    return await execute_case_retry(case_id, user=user)


@router.post("/cases/{case_id}/confirm-parsing", response_model=ConfirmParsingResponse)
async def confirm_parsing(
    case_id: UUID,
    body: ConfirmParsingRequest,
    user: TokenData = Depends(require_permission("cases:write")),
) -> ConfirmParsingResponse:
    return await execute_confirm_parsing(case_id, user=user, body=body)


@router.post("/cases/{case_id}/reject-parsing", response_model=RejectParsingResponse)
async def reject_parsing(
    case_id: UUID,
    body: RejectParsingRequest,
    user: TokenData = Depends(require_permission("cases:write")),
) -> RejectParsingResponse:
    return await execute_reject_parsing(case_id, user=user, body=body)


@router.get("/cases/{case_id}/timeline")
async def get_case_timeline(
    case_id: UUID,
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[TimelineEntryResponse]:
    repo = CaseRepository(session)
    case = await repo.get(case_id)
    if not case:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found")
    entries = sorted(case.timeline, key=lambda t: t.created_at)
    user_ids = {t.actor_user_id for t in entries if t.actor_user_id}
    users_by_id: dict[UUID, User] = {}
    if user_ids:
        rows = await session.scalars(select(User).where(User.id.in_(user_ids)))
        users_by_id = {u.id: u for u in rows}

    out: list[TimelineEntryResponse] = []
    for entry in entries:
        row = TimelineEntryResponse.model_validate(entry)
        out.append(
            row.model_copy(
                update={"actor": resolve_timeline_actor_display(entry, users_by_id)}
            )
        )
    return out


@router.get("/workflow/queues", response_model=QueueStatusResponse)
async def queue_status(
    _user: TokenData = Depends(require_permission("cases:read")),
) -> QueueStatusResponse:
    return await _queue_status()


@router.post("/policies/evaluate")
async def evaluate_policies(
    case_id: UUID = Query(...),
    _user: TokenData = Depends(require_permission("policies:read")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    service = CaseService(session)
    case = await service.get_case(case_id)
    action = await service.evaluate_policies(case)
    policies = await PolicyRepository(session).list_active(policy_type="approval")
    return {"action": action, "matched_policies": len(policies)}
