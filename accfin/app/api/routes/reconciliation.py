"""Reconciliation API — `05` §13."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.core.exceptions import AppHTTPException
from app.repositories.reconciliation import ReconciliationRepository
from app.schemas.auth import TokenData
from app.schemas.reconciliation import (
    ReconciliationRunResponse,
    StartReconciliationRequest,
    StartReconciliationResponse,
    UnmatchedItemResponse,
    UnmatchedItemsResponse,
)
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post(
    "/start",
    response_model=StartReconciliationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_reconciliation(
    body: StartReconciliationRequest,
    user: TokenData = Depends(require_permission("reconciliation:write")),
    session: AsyncSession = Depends(get_db_session),
) -> StartReconciliationResponse:
    service = ReconciliationService(session)
    run_id, run_status = await service.start_reconciliation(body, started_by=user.user_id)
    return StartReconciliationResponse(
        reconciliation_id=run_id,
        status=run_status,
        estimated_completion=ReconciliationService.estimated_completion(),
    )


@router.get("/{reconciliation_id}", response_model=ReconciliationRunResponse)
async def get_reconciliation(
    reconciliation_id: UUID,
    _user: TokenData = Depends(require_permission("reconciliation:read")),
    session: AsyncSession = Depends(get_db_session),
) -> ReconciliationRunResponse:
    repo = ReconciliationRepository(session)
    run = await repo.get_run(reconciliation_id)
    if run is None:
        raise AppHTTPException(404, "NOT_FOUND", "Reconciliation run not found")
    return ReconciliationRunResponse.model_validate(run)


@router.get("/{reconciliation_id}/unmatched", response_model=UnmatchedItemsResponse)
async def get_unmatched_items(
    reconciliation_id: UUID,
    _user: TokenData = Depends(require_permission("reconciliation:read")),
    session: AsyncSession = Depends(get_db_session),
) -> UnmatchedItemsResponse:
    repo = ReconciliationRepository(session)
    run = await repo.get_run(reconciliation_id)
    if run is None:
        raise AppHTTPException(404, "NOT_FOUND", "Reconciliation run not found")

    bank = await repo.list_unmatched_bank(reconciliation_id)
    ledger = await repo.list_unmatched_ledger(reconciliation_id)
    items = [
        UnmatchedItemResponse(
            id=b.id,
            side="bank",
            transaction_date=b.transaction_date,
            description=b.description,
            reference=b.reference,
            amount=str(b.amount),
            currency=b.currency,
        )
        for b in bank
    ] + [
        UnmatchedItemResponse(
            id=l.id,
            side="ledger",
            transaction_date=l.transaction_date,
            description=l.description,
            reference=l.reference,
            amount=str(l.amount),
            currency=l.currency,
        )
        for l in ledger
    ]
    return UnmatchedItemsResponse(
        reconciliation_id=reconciliation_id,
        unmatched_count=len(items),
        items=items,
    )
