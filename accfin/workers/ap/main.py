"""AP Worker service — port 8012."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import check_database, get_session_factory
from app.core.redis_client import check_redis, get_redis
from workers.ap.worker import APQueueConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ap-worker")

settings = get_settings()
app = FastAPI(title="AP Worker", version=settings.version)


@app.get("/health")
async def health() -> dict:
    redis = get_redis()
    return {
        "status": "ok",
        "service": "ap-worker",
        "components": {
            "database": await check_database(),
            "redis": await check_redis(),
        },
        "queues": {
            "accounts": await redis.llen(settings.accounts_queue_name),
        },
    }


async def _consumer_loop() -> None:
    factory = get_session_factory()
    redis = get_redis()
    consumer = APQueueConsumer(redis)
    while True:
        try:
            async with factory() as session:
                worked = await consumer.poll_once(session)
            if not worked:
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("AP worker poll error")
            await asyncio.sleep(1)


@app.on_event("startup")
async def startup() -> None:
    if settings.ap_worker_enabled:
        asyncio.create_task(_consumer_loop())


@app.post("/process-once", include_in_schema=False)
async def process_once() -> dict:
    redis = get_redis()
    factory = get_session_factory()
    async with factory() as session:
        worked = await APQueueConsumer(redis).poll_once(session)
    return {"processed": worked}
