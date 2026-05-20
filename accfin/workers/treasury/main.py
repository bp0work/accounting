"""Treasury Worker service — port 8013 (reconciliation runs, not queue-driven)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_database, get_session_factory
from app.core.redis_client import check_redis
from workers.treasury.worker import TreasuryWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("treasury-worker")

settings = get_settings()
app = FastAPI(title="Treasury Worker", version=settings.version)


class RunReconciliationBody(BaseModel):
    reconciliation_id: UUID


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "treasury-worker",
        "components": {
            "database": await check_database(),
            "redis": await check_redis(),
        },
    }


@app.post("/reconciliation/run", include_in_schema=False)
async def run_reconciliation(body: RunReconciliationBody) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        worker = TreasuryWorker(session)
        return await worker.run_reconciliation(body.reconciliation_id)
