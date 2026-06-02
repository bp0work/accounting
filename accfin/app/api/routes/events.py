"""SSE event stream — `05` §9a, `09` §15."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies import get_current_user
from app.core.jwt import decode_access_token
from app.core.redis_client import get_redis
from app.schemas.auth import TokenData

router = APIRouter(tags=["Events"])
bearer_scheme = HTTPBearer(auto_error=False)


def _token_data_from_access_token(token: str) -> TokenData:
    from uuid import UUID

    payload = decode_access_token(token)
    return TokenData(
        user_id=UUID(str(payload["sub"])),
        role=str(payload["role"]),
        permissions=list(payload.get("permissions") or []),
    )


async def _resolve_sse_user(
    token: str | None,
    credentials: HTTPAuthorizationCredentials | None,
) -> TokenData:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return await get_current_user(credentials)
    if token:
        user = _token_data_from_access_token(token)
        if "cases:read" not in user.permissions and "tenant:admin" not in user.permissions:
            from app.core.exceptions import AppHTTPException
            from fastapi import status

            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "INSUFFICIENT_PERMISSION",
                "cases:read is required",
            )
        return user
    from app.core.exceptions import AppHTTPException
    from fastapi import status

    raise AppHTTPException(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "No valid token provided")


@router.get("/events/stream")
async def event_stream(
    token: str | None = Query(None, description="JWT for EventSource clients (no Authorization header)"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> StreamingResponse:
    user = await _resolve_sse_user(token, credentials)
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
