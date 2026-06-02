"""Redis pub/sub for SSE — `09` §15."""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


async def publish_user_event(user_id: str, event_type: str, data: dict) -> None:
    """Publish an SSE payload to the user's channel."""
    try:
        redis = get_redis()
        payload = {
            "event": event_type,
            "id": f"evt-{uuid4().hex[:12]}",
            "data": data,
        }
        await redis.publish(f"finance:user:{user_id}", json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish SSE event %s", event_type)


async def publish_broadcast_event(event_type: str, data: dict) -> None:
    """Publish an SSE payload to all finance subscribers."""
    try:
        redis = get_redis()
        payload = {
            "event": event_type,
            "id": f"evt-{uuid4().hex[:12]}",
            "data": data,
        }
        await redis.publish("finance:broadcast", json.dumps(payload))
    except Exception:
        logger.exception("Failed to publish broadcast SSE event %s", event_type)
