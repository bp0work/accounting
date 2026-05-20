"""SSE event stream — `05` §9a, `09` §15."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.dependencies import require_permission
from app.core.redis_client import get_redis
from app.schemas.auth import TokenData

router = APIRouter(tags=["Events"])


@router.get("/events/stream")
async def event_stream(
    user: TokenData = Depends(require_permission("cases:read")),
) -> StreamingResponse:
    channel = f"finance:user:{user.user_id}"

    async def generate():
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        yield "event: connected\ndata: {}\n\n"
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    payload = json.loads(message["data"])
                    event_type = payload.get("event", "message")
                    event_id = payload.get("id", "")
                    data = json.dumps(payload.get("data", {}))
                    yield f"event: {event_type}\nid: {event_id}\ndata: {data}\n\n"
                await asyncio.sleep(0.05)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
