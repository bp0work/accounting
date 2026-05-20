"""Case and workflow API — Phase 4."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.core.redis_client import get_redis
from app.core.config import get_settings
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.schemas.case import (
    CaseListResponse,
    CaseResponse,
    CaseStatusTransitionRequest,
    CaseStatusTransitionResponse,
    QueueStatusResponse,
    TimelineEntryResponse,
)
from app.repositories.policy import PolicyRepository
from app.services.case_service import CaseService

router = APIRouter(tags=["Cases"])


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    limit: int = Query(default=50, ge=1, le=100),
    status: str | None = Query(default=None),
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseListResponse:
    service = CaseService(session)
    cases = await service.list_cases(limit=limit, status_filter=status)
    return CaseListResponse(data=[CaseResponse.model_validate(c) for c in cases])


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> CaseResponse:
    service = CaseService(session)
    case = await service.get_case(case_id)
    return CaseResponse.model_validate(case)


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
        from app.core.exceptions import AppHTTPException
        from fastapi import status

        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found")
    return [TimelineEntryResponse.model_validate(t) for t in case.timeline]


@router.get("/workflow/queues", response_model=QueueStatusResponse)
async def queue_status(
    _user: TokenData = Depends(require_permission("cases:read")),
) -> QueueStatusResponse:
    settings = get_settings()
    redis = get_redis()
    retry_count = await redis.zcard(settings.retry_queue_name)
    return QueueStatusResponse(
        intake_queue=await redis.llen(settings.intake_queue_name),
        accounts_queue=await redis.llen(settings.accounts_queue_name),
        dead_letter_queue=await redis.llen(settings.dead_letter_queue_name),
        retry_queue_pending=retry_count,
    )


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
