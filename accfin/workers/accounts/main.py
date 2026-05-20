"""Accounts Worker service — port 8010."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import check_database, get_session_factory
from app.core.redis_client import check_redis, get_redis
from workers.accounts.worker import AccountsQueueConsumer, IntakeConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("accounts-worker")

settings = get_settings()
app = FastAPI(title="Accounts Worker", version=settings.version)


@app.get("/health")
async def health() -> dict:
    redis = get_redis()
    return {
        "status": "ok",
        "service": "accounts-worker",
        "components": {
            "database": await check_database(),
            "redis": await check_redis(),
        },
        "queues": {
            "intake": await redis.llen(settings.intake_queue_name),
            "accounts": await redis.llen(settings.accounts_queue_name),
        },
    }


async def _consumer_loop(consumer: IntakeConsumer | AccountsQueueConsumer) -> None:
    factory = get_session_factory()
    while True:
        try:
            async with factory() as session:
                worked = await consumer.poll_once(session)
            if not worked:
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("%s poll error", consumer.worker_name)
            await asyncio.sleep(1)


@app.on_event("startup")
async def startup() -> None:
    if settings.accounts_worker_enabled:
        redis = get_redis()
        asyncio.create_task(_consumer_loop(IntakeConsumer(redis)))
        asyncio.create_task(_consumer_loop(AccountsQueueConsumer(redis)))


@app.post("/process-intake-once", include_in_schema=False)
async def process_intake_once() -> dict:
    redis = get_redis()
    factory = get_session_factory()
    async with factory() as session:
        worked = await IntakeConsumer(redis).poll_once(session)
    return {"processed": worked}
