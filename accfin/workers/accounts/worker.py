"""Accounts Worker queue consumers — `17` §3."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient
from app.core.config import get_settings
from workers.accounts.classification import GeneralInquiryHandler, process_intake_message
from workers.base import QueueConsumer

logger = logging.getLogger(__name__)


class IntakeConsumer(QueueConsumer):
    def __init__(self, redis, hermes: HermesClient | None = None) -> None:
        settings = get_settings()
        super().__init__(redis, settings.intake_queue_name, "accounts-worker")
        self._hermes = hermes

    async def handle_raw(self, raw: str, session: AsyncSession) -> dict[str, Any]:
        # DB work uses per-phase sessions inside process_intake_message (see poller fix).
        return await process_intake_message(raw, hermes=self._hermes)


class AccountsQueueConsumer(QueueConsumer):
    def __init__(self, redis) -> None:
        settings = get_settings()
        super().__init__(
            redis,
            settings.accounts_queue_name,
            "accounts-worker",
            accepted_case_types=frozenset({"general_inquiry"}),
        )

    async def handle_raw(self, raw: str, session: AsyncSession) -> dict[str, Any]:
        message = json.loads(raw)
        case_type = message.get("case_type")
        if case_type == "general_inquiry":
            return await GeneralInquiryHandler(session).process(message)
        return {"status": "skipped", "reason": "delegated_to_domain_worker", "case_type": case_type}
