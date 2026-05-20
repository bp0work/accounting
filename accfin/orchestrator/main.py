"""Workflow Orchestrator — retry/DLQ (port 8003). Intake is consumed by Accounts Worker."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import check_database
from app.core.redis_client import check_redis, get_redis
from app.services.queue_router import pop_due_retries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

settings = get_settings()
app = FastAPI(title="Workflow Orchestrator", version=settings.version)


@app.get("/health")
async def health() -> dict:
    redis = get_redis()
    intake_depth = await redis.llen(settings.intake_queue_name)
    accounts_depth = await redis.llen(settings.accounts_queue_name)
    dlq_depth = await redis.llen(settings.dead_letter_queue_name)
    return {
        "status": "ok",
        "service": "orchestrator",
        "components": {
            "database": await check_database(),
            "redis": await check_redis(),
        },
        "queues": {
            "intake": intake_depth,
            "accounts": accounts_depth,
            "dead_letter": dlq_depth,
        },
        "intake_consumer": "accounts-worker",
    }


async def _process_retries_once() -> int:
    items = await pop_due_retries(limit=10)
    if not items:
        return 0
    redis = get_redis()
    requeued = 0
    for item in items:
        inner = item.get("payload", {})
        raw = inner.get("raw")
        if not raw:
            continue
        target = inner.get("queue_target", "intake")
        queue = (
            settings.accounts_queue_name
            if target == "accounts"
            else settings.intake_queue_name
        )
        await redis.rpush(queue, raw)
        requeued += 1
    return requeued


async def _consumer_loop() -> None:
    while True:
        if settings.orchestrator_enabled:
            try:
                await _process_retries_once()
            except Exception:
                logger.exception("Retry loop error")
        await asyncio.sleep(2)


@app.on_event("startup")
async def startup() -> None:
    if settings.orchestrator_enabled:
        asyncio.create_task(_consumer_loop())


@app.post("/process-retries-once", include_in_schema=False)
async def process_retries_once() -> dict:
    count = await _process_retries_once()
    return {"retries_requeued": count}
