"""Push to Redis intake_queue — `17` §2.2."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.core.redis_client import get_redis

INTAKE_QUEUE = "intake_queue"


async def enqueue_intake(*, email_id: UUID, mailbox: str) -> str:
    message_id = str(uuid4())
    payload = {
        "message_id": message_id,
        "email_id": str(email_id),
        "mailbox": mailbox,
        "enqueued_at": datetime.now(UTC).isoformat(),
    }
    redis = get_redis()
    await redis.rpush(get_settings().intake_queue_name, json.dumps(payload))
    return message_id
