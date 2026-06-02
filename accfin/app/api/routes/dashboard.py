"""Operations dashboard stats — `0.15.09-dashboard-redesign`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.schemas.auth import TokenData
from app.schemas.dashboard import DashboardStatsResponse
from app.services.dashboard_stats import build_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def dashboard_stats(
    user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardStatsResponse:
    return await build_dashboard_stats(session, user=user)
