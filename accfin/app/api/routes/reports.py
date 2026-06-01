"""Financial reports API."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.schemas.auth import TokenData
from app.schemas.trial_balance import TrialBalanceResponse
from app.services.trial_balance import build_trial_balance, trial_balance_to_csv

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    as_at: date | None = Query(None, description="As-at date (ISO); defaults to today"),
    session: AsyncSession = Depends(get_db_session),
    _: TokenData = Depends(require_permission("reports:read")),
) -> TrialBalanceResponse:
    effective = as_at or date.today()
    return await build_trial_balance(session, as_at=effective)


@router.get("/trial-balance/export")
async def export_trial_balance_csv(
    as_at: date | None = Query(None, description="As-at date (ISO); defaults to today"),
    session: AsyncSession = Depends(get_db_session),
    _: TokenData = Depends(require_permission("reports:read")),
) -> StreamingResponse:
    effective = as_at or date.today()
    report = await build_trial_balance(session, as_at=effective)
    csv_text = trial_balance_to_csv(report)
    filename = f"trial_balance_{effective.isoformat()}.csv"
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
