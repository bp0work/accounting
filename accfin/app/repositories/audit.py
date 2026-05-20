"""Audit log persistence — `06` §13.1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_last_hash(self) -> str | None:
        stmt = (
            select(AuditLog.tamper_hash)
            .order_by(AuditLog.timestamp.desc(), AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def append(self, entry: AuditLog) -> AuditLog:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_by_id(self, entry_id: UUID) -> AuditLog | None:
        result = await self._session.execute(select(AuditLog).where(AuditLog.id == entry_id))
        return result.scalar_one_or_none()

    def _filtered(
        self,
        *,
        entity_type: str | None,
        entity_id: UUID | None,
        action: str | None,
        user_id: UUID | None,
        from_date: datetime | None,
        to_date: datetime | None,
        actions: list[str] | None,
    ) -> Select:
        stmt = select(AuditLog)
        clauses = []
        if entity_type:
            clauses.append(AuditLog.entity_type == entity_type)
        if entity_id:
            clauses.append(AuditLog.entity_id == entity_id)
        if action:
            clauses.append(AuditLog.action == action)
        if actions:
            clauses.append(AuditLog.action.in_(actions))
        if user_id:
            clauses.append(AuditLog.user_id == user_id)
        if from_date:
            clauses.append(AuditLog.timestamp >= from_date)
        if to_date:
            clauses.append(AuditLog.timestamp <= to_date)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        return stmt.order_by(AuditLog.timestamp.desc(), AuditLog.created_at.desc(), AuditLog.id.desc())

    async def list_entries(
        self,
        *,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        action: str | None = None,
        user_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        actions: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = self._filtered(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            actions=actions,
        ).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_entries(
        self,
        *,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        action: str | None = None,
        user_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        actions: list[str] | None = None,
    ) -> int:
        base = self._filtered(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            actions=actions,
        ).subquery()
        result = await self._session.execute(select(func.count()).select_from(base))
        return int(result.scalar_one())

    async def iter_chain_ordered(self, *, limit: int | None = None) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(
            AuditLog.timestamp.asc(), AuditLog.created_at.asc(), AuditLog.id.asc()
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
