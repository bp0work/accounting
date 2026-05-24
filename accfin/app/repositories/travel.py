"""Travel request lookup for expense claim matching."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.travel import TravelRequest


class TravelRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_approved_for_period(
        self,
        *,
        employee_id: UUID,
        period_from: date,
        period_to: date,
    ) -> TravelRequest | None:
        """Return an approved travel request overlapping the claim period."""
        result = await self._session.execute(
            select(TravelRequest)
            .where(
                TravelRequest.employee_id == employee_id,
                TravelRequest.status == "approved",
                TravelRequest.travel_from <= period_to,
                TravelRequest.travel_to >= period_from,
            )
            .order_by(TravelRequest.travel_from.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
