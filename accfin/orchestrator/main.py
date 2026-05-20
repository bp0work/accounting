"""Workflow Orchestrator — intake consumer, retry, queue routing (port 8003)."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import check_database, get_session_factory
from app.core.redis_client import check_redis, get_redis
from app.services.intake_processor import IntakeProcessor
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
    }


async def _process_intake_once() -> bool:
    redis = get_redis()
    item = await redis.blpop(settings.intake_queue_name, timeout=1)
    if not item:
        return False
    _key, raw = item
    factory = get_session_factory()
    retry_count = 0
    try:
        payload = json.loads(raw)
        retry_count = int(payload.get("retry_count", 0))
    except json.JSONDecodeError:
        pass

    async with factory() as session:
        processor = IntakeProcessor(session)
        try:
            result = await processor.process_message(raw)
            logger.info("Intake processed: %s", result)
        except Exception as exc:
            logger.exception("Intake processing failed")
            await session.rollback()
            processor = IntakeProcessor(session)
            await processor.handle_failure(raw, str(exc), retry_count)
    return True


async def _process_retries_once() -> int:
    items = await pop_due_retries(limit=5)
    if not items:
        return 0
    redis = get_redis()
    for item in items:
        inner = item.get("payload", {})
        raw = inner.get("raw")
        if raw:
            await redis.rpush(settings.intake_queue_name, raw)
    return len(items)


async def _consumer_loop() -> None:
    while True:
        if settings.orchestrator_enabled:
            try:
                worked = await _process_intake_once()
                if not worked:
                    await _process_retries_once()
            except Exception:
                logger.exception("Consumer loop error")
        await asyncio.sleep(0.5 if settings.orchestrator_enabled else 2)


@app.on_event("startup")
async def startup() -> None:
    if settings.orchestrator_enabled:
        asyncio.create_task(_consumer_loop())


@app.post("/process-once", include_in_schema=False)
async def process_once() -> dict:
    """Manual trigger for tests."""
    processed = await _process_intake_once()
    retries = await _process_retries_once()
    return {"intake_processed": processed, "retries_requeued": retries}
