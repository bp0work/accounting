"""Mail Gateway service — IMAP poll loop on port 8002."""

import asyncio
import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import check_database
from app.core.redis_client import check_redis
from gateway.imap.poller import poll_all_executive_mailboxes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

settings = get_settings()

app = FastAPI(title="Mail Gateway", version=settings.version)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "mail-gateway",
        "components": {
            "database": await check_database(),
            "redis": await check_redis(),
        },
    }


@app.post("/poll", include_in_schema=False)
async def trigger_poll() -> dict:
    results = await poll_all_executive_mailboxes()
    return {"polled": results}


async def _poll_loop() -> None:
    interval = settings.mail_poll_interval_seconds
    while True:
        if settings.mail_poll_enabled:
            try:
                await poll_all_executive_mailboxes()
            except Exception:
                logger.exception("Poll loop error")
        await asyncio.sleep(interval)


@app.on_event("startup")
async def startup() -> None:
    if settings.mail_poll_enabled:
        asyncio.create_task(_poll_loop())
