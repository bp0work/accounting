"""Redis queue routing — intake → accounts / DLQ / retry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.core.queues import ACCOUNTS_QUEUE, DEAD_LETTER_QUEUE, RETRY_QUEUE
from app.core.redis_client import get_redis


async def enqueue_accounts(
    *,
    case_id: UUID,
    case_type: str,
    case_number: str,
    email_id: UUID | None = None,
    priority: str = "medium",
    stp_eligible: bool = False,
    confidence_score: float = 0.0,
    retry_count: int = 0,
    source: str = "accounts-worker",
) -> str:
    message_id = str(uuid4())
    payload = {
        "message_id": message_id,
        "case_id": str(case_id),
        "case_type": case_type,
        "case_number": case_number,
        "email_id": str(email_id) if email_id else None,
        "priority": priority,
        "stp_eligible": stp_eligible,
        "confidence_score": confidence_score,
        "enqueued_at": datetime.now(UTC).isoformat(),
        "retry_count": retry_count,
        "retry_config": {
            "max_attempts": 3,
            "previous_error": None,
            "previous_error_type": None,
        },
        "source": source,
    }
    redis = get_redis()
    await redis.rpush(get_settings().accounts_queue_name, json.dumps(payload))
    return message_id


async def enqueue_dead_letter(*, payload: dict, reason: str) -> str:
    message_id = str(uuid4())
    body = {
        "message_id": message_id,
        "reason": reason,
        "failed_at": datetime.now(UTC).isoformat(),
        "original": payload,
    }
    redis = get_redis()
    await redis.rpush(get_settings().dead_letter_queue_name, json.dumps(body))
    return message_id


async def schedule_retry(*, payload: dict, delay_seconds: int) -> str:
    """Add to retry sorted set; score = unix time when due."""
    message_id = str(uuid4())
    body = {
        "message_id": message_id,
        "retry_at": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    redis = get_redis()
    due = datetime.now(UTC).timestamp() + delay_seconds
    await redis.zadd(get_settings().retry_queue_name, {json.dumps(body): due})
    return message_id


async def pop_due_retries(limit: int = 10) -> list[dict[str, Any]]:
    redis = get_redis()
    now = datetime.now(UTC).timestamp()
    key = get_settings().retry_queue_name
    raw_items = await redis.zrangebyscore(key, "-inf", now, start=0, num=limit)
    results: list[dict[str, Any]] = []
    for raw in raw_items:
        await redis.zrem(key, raw)
        results.append(json.loads(raw))
    return results
