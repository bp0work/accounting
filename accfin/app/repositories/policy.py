"""Policy persistence — Phase 4."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy


class PolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self, policy_type: str | None = None) -> list[Policy]:
        q = select(Policy).where(Policy.is_active.is_(True)).order_by(Policy.name, Policy.version.desc())
        if policy_type:
            q = q.where(Policy.policy_type == policy_type)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get(self, policy_id) -> Policy | None:
        result = await self._session.execute(select(Policy).where(Policy.id == policy_id))
        return result.scalar_one_or_none()
