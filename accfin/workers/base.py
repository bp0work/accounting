"""Shared worker infrastructure — `17` §2.4, §8."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.case import Case

logger = logging.getLogger(__name__)

TERMINAL_CASE_STATUSES = frozenset({"posted", "completed", "pending_approval"})

# Block up to N seconds on BLPOP when the queue is empty (avoids tight Redis poll loops).
DEFAULT_QUEUE_BLOCK_TIMEOUT_SEC = 5


async def check_idempotent(redis: Redis, message_id: str) -> bool:
    """Return True if this message should be processed (new), False if duplicate."""
    key = f"worker:processed:{message_id}"
    newly_set = await redis.set(key, "1", nx=True, ex=86400)
    return bool(newly_set)


async def late_retry_guard(session: AsyncSession, case_id: UUID | None) -> bool:
    """Return True if processing should continue."""
    if case_id is None:
        return True
    result = await session.execute(select(Case.status).where(Case.id == case_id))
    status = result.scalar_one_or_none()
    if status in TERMINAL_CASE_STATUSES:
        logger.info("Case %s in terminal state %s — skipping", case_id, status)
        return False
    return True


async def signal_retry(
    redis: Redis,
    *,
    case_id: str | None,
    error_type: str,
    delay_seconds: int = 60,
    queue_target: str = "intake",
) -> None:
    settings = get_settings()
    score = datetime.now(UTC).timestamp() + delay_seconds
    payload = json.dumps(
        {
            "case_id": case_id,
            "error_type": error_type,
            "queue_target": queue_target,
        }
    )
    await redis.zadd(settings.retry_queue_name, {payload: score})


class QueueConsumer(ABC):
    """Blocking BLPOP loop for a single Redis queue."""

    def __init__(
        self,
        redis: Redis,
        queue_name: str,
        worker_name: str,
        *,
        accepted_case_types: frozenset[str] | None = None,
    ) -> None:
        self.redis = redis
        self.queue_name = queue_name
        self.worker_name = worker_name
        self.accepted_case_types = accepted_case_types

    @abstractmethod
    async def handle_raw(self, raw: str, session: AsyncSession) -> dict[str, Any]:
        ...

    async def poll_once(
        self,
        session: AsyncSession,
        *,
        timeout: int = DEFAULT_QUEUE_BLOCK_TIMEOUT_SEC,
    ) -> bool:
        item = await self.redis.blpop(self.queue_name, timeout=timeout)
        if not item:
            return False
        _key, raw = item
        try:
            payload = json.loads(raw)
            case_type = payload.get("case_type")
            if self.accepted_case_types is not None and case_type not in self.accepted_case_types:
                await self.redis.rpush(self.queue_name, raw)
                return True
            message_id = payload.get("message_id", "")
            if message_id and not await check_idempotent(self.redis, message_id):
                logger.info("%s duplicate %s — skip", self.worker_name, message_id)
                return True
            case_id = payload.get("case_id")
            if case_id and not await late_retry_guard(session, UUID(str(case_id))):
                return True
            result = await self.handle_raw(raw, session)
            await session.commit()
            logger.info("%s handled message: %s", self.worker_name, result)
        except Exception:
            await session.rollback()
            raise
        return True
