"""Redis queue routing — intake → accounts / DLQ / retry."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.queues import ACCOUNTS_QUEUE, DEAD_LETTER_QUEUE, RETRY_QUEUE
from app.core.redis_client import get_redis
from app.models.case import Case

logger = logging.getLogger(__name__)


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
    override_po_check: bool = False,
    override_policy: bool = False,
    gl_period_override: bool = False,
    gl_period_override_reason: str | None = None,
    gl_period_posted_by: str | None = None,
    message_id: str | None = None,
    parsing_confirmed: bool = False,
) -> str:
    message_id = message_id or str(uuid4())
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
    if override_po_check:
        payload["override_po_check"] = True
    if override_policy:
        payload["override_policy"] = True
    if gl_period_override:
        payload["gl_period_override"] = True
        if gl_period_override_reason:
            payload["gl_period_override_reason"] = gl_period_override_reason
        if gl_period_posted_by:
            payload["gl_period_posted_by"] = gl_period_posted_by
    if parsing_confirmed:
        payload["parsing_confirmed"] = True
    redis = get_redis()
    await redis.rpush(get_settings().accounts_queue_name, json.dumps(payload))
    return message_id


async def route_case_to_queue(
    *,
    case: Case,
    session: AsyncSession | None = None,
    email_id: UUID | None = None,
    confidence_score: float | None = None,
    source: str = "accounts-worker",
) -> str:
    """
    Push a classified case onto accounts_queue for domain workers (AP, AR, expense, treasury).

    AP/AR/expense workers BLPOP the same queue and filter by `case_type`.
    """
    score = confidence_score if confidence_score is not None else float(case.confidence_score or 0)
    resolved_email_id = email_id if email_id is not None else case.email_id
    message_id = await enqueue_accounts(
        case_id=case.id,
        case_type=case.type,
        case_number=case.case_number,
        email_id=resolved_email_id,
        priority=case.priority or "medium",
        stp_eligible=bool(case.stp_eligible),
        confidence_score=score,
        source=source,
    )
    logger.info(
        "Routed %s (%s) to %s message_id=%s",
        case.case_number,
        case.type,
        get_settings().accounts_queue_name,
        message_id,
    )
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
