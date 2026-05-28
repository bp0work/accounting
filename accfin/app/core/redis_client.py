"""Shared async Redis client — used by API, gateway, orchestrator, and workers."""

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,
            socket_timeout=30,
            socket_connect_timeout=10,
            socket_keepalive=True,
            socket_keepalive_options={},
            retry_on_timeout=True,
        )
    return _redis


async def check_redis() -> str:
    redis = get_redis()
    pong = await redis.ping()
    return "ok" if pong else "error"
