"""AP Worker accounts_queue consumer — `17` §5."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient
from app.core.config import get_settings
from workers.ap.handlers import AP_CASE_TYPES, APWorkerService
from workers.base import QueueConsumer

logger = logging.getLogger(__name__)


class APQueueConsumer(QueueConsumer):
    def __init__(self, redis, hermes: HermesClient | None = None) -> None:
        settings = get_settings()
        super().__init__(
            redis,
            settings.accounts_queue_name,
            "ap-worker",
            accepted_case_types=AP_CASE_TYPES,
        )
        self._hermes = hermes

    async def handle_raw(self, raw: str, session: AsyncSession) -> dict[str, Any]:
        message = json.loads(raw)
        service = APWorkerService(session, hermes=self._hermes)
        return await service.process_accounts_message(message)
