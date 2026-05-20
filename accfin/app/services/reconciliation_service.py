"""Reconciliation orchestration — `05` §13, `17` §6."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.repositories.reconciliation import ReconciliationRepository
from app.schemas.reconciliation import BankItemInput, StartReconciliationRequest
from workers.treasury.worker import TreasuryWorker


class ReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ReconciliationRepository(session)

    async def start_reconciliation(
        self, request: StartReconciliationRequest, *, started_by: UUID
    ) -> tuple[UUID, str]:
        account = await self._repo.get_account(request.account_id)
        if account is None:
            raise AppHTTPException(404, "ACCOUNT_NOT_FOUND", "COA account not found")
        if not account.is_bank_account:
            raise AppHTTPException(
                400,
                "INVALID_ACCOUNT",
                "Reconciliation requires a bank COA account",
            )

        opening = Decimal(request.opening_balance)
        statement_balance = (
            Decimal(request.statement_balance) if request.statement_balance is not None else None
        )

        run = await self._repo.create_run(
            account_id=request.account_id,
            period_from=request.statement_period_from,
            period_to=request.statement_period_to,
            started_by=started_by,
            opening_balance=opening,
            statement_balance=statement_balance,
        )

        if request.bank_items:
            await self._repo.add_bank_items(
                run.id,
                [self._bank_item_dict(item) for item in request.bank_items],
            )

        await self._repo.load_ledger_items_from_journals(
            run.id,
            request.account_id,
            request.statement_period_from,
            request.statement_period_to,
        )
        await self._repo.set_run_totals(run)
        await self._session.commit()

        asyncio.create_task(self._run_async(run.id))
        return run.id, run.status

    async def _run_async(self, run_id: UUID) -> None:
        from app.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            worker = TreasuryWorker(session)
            await worker.run_reconciliation(run_id)

    @staticmethod
    def _bank_item_dict(item: BankItemInput) -> dict:
        return {
            "transaction_date": item.transaction_date,
            "description": item.description,
            "reference": item.reference,
            "amount": item.amount,
            "currency": item.currency,
        }

    @staticmethod
    def estimated_completion() -> str:
        return (datetime.now(UTC) + timedelta(minutes=20)).isoformat()
