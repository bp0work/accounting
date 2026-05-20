"""AR Worker accounts_queue consumer — `17` §4."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient
from app.core.config import get_settings
from workers.ar.handlers import AR_CASE_TYPES, ARWorkerService
from workers.base import QueueConsumer

logger = logging.getLogger(__name__)


class ARQueueConsumer(QueueConsumer):
    def __init__(self, redis, hermes: HermesClient | None = None) -> None:
        settings = get_settings()
        super().__init__(
            redis,
            settings.accounts_queue_name,
            "ar-worker",
            accepted_case_types=AR_CASE_TYPES,
        )
        self._hermes = hermes

    async def handle_raw(self, raw: str, session: AsyncSession) -> dict[str, Any]:
        message = json.loads(raw)
        service = ARWorkerService(session, hermes=self._hermes)
        return await service.process_accounts_message(message)
