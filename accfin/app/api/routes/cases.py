"""Case and workflow API — Phase 4; finance oversight dashboard."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.core.exceptions import AppHTTPException
from app.core.redis_client import get_redis
from app.repositories.case import CaseRepository
from app.repositories.policy import PolicyRepository
from app.schemas.auth import TokenData
from app.schemas.case import (
    CaseDashboardResponse,
    CaseListResponse,
    CaseResponse,
    CaseStatusTransitionRequest,
    CaseStatusTransitionResponse,
    QueueStatusResponse,
    TimelineEntryResponse,
)
from app.services.case_export import build_cases_csv
from app.services.case_metrics import is_case_overdue, processing_time_minutes
from app.services.case_service import CaseService
from fastapi import status

router = APIRouter(tags=["Cases"])


def _case_response(case) -> CaseResponse:
    base = CaseResponse.model_validate(case)
    return base.model_copy(
        update={
            "completed_at": case.completed_at,
            "sla_deadline": case.sla_deadline,
            "processing_time_minutes": processing_time_minutes(case),
            "is_overdue": is_case_overdue(case),
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
    return CaseDashboardResponse(
        queue_depths=await _queue_status(),
        cases_by_status=await repo.count_by_status(),
        average_processing_time_minutes=await repo.average_processing_minutes_completed(),
        overdue_count=len(overdue),
        overdue_cases=[_case_response(c) for c in overdue],
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
    return CaseListResponse(data=[_case_response(c) for c in cases])


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseResponse:
    service = CaseService(session)
    case = await service.get_case(case_id)
    return _case_response(case)


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
    return [TimelineEntryResponse.model_validate(t) for t in case.timeline]


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
