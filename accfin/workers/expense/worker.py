"""Expense Worker accounts_queue consumer — `19` §2."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient
from app.core.config import get_settings
from workers.base import QueueConsumer
from workers.expense.handlers import EXPENSE_CASE_TYPES, ExpenseWorkerService

logger = logging.getLogger(__name__)


class ExpenseQueueConsumer(QueueConsumer):
    def __init__(self, redis, hermes: HermesClient | None = None) -> None:
        settings = get_settings()
        super().__init__(
            redis,
            settings.accounts_queue_name,
            "expense-worker",
            accepted_case_types=EXPENSE_CASE_TYPES,
        )
        self._hermes = hermes

    async def handle_raw(self, raw: str, session: AsyncSession) -> dict[str, Any]:
        message = json.loads(raw)
        service = ExpenseWorkerService(session, hermes=self._hermes)
        return await service.process_accounts_message(message)
