"""Treasury reconciliation worker — `17` §6."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient, HermesError
from app.core.config import get_settings
from app.repositories.reconciliation import ReconciliationRepository
from app.schemas.hermes import (
    ReconciliationBankItem as HermesBankItem,
    ReconciliationLedgerItem as HermesLedgerItem,
    SuggestMatchesRequest,
)
from workers.treasury.matching import find_rule_based_matches

logger = logging.getLogger(__name__)


class TreasuryWorker:
    def __init__(self, session: AsyncSession, hermes: HermesClient | None = None) -> None:
        self._session = session
        self._hermes = hermes or HermesClient()
        self._repo = ReconciliationRepository(session)
        self._settings = get_settings()

    async def run_reconciliation(self, reconciliation_id: UUID) -> dict:
        run = await self._repo.get_run(reconciliation_id)
        if run is None:
            return {"status": "skipped", "reason": "run_not_found"}

        if run.status == "completed":
            logger.info("Reconciliation %s already completed — skipping", reconciliation_id)
            return {"status": "skipped", "reason": "already_completed"}

        if run.status == "in_progress" and run.started_at and run.match_rules_used:
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            age = datetime.now(UTC) - started
            if age < timedelta(minutes=10):
                logger.warning(
                    "Reconciliation %s already in progress — skipping dispatch", reconciliation_id
                )
                return {"status": "skipped", "reason": "already_in_progress"}

        account = await self._repo.get_account(run.account_id)
        if account is None:
            await self._repo.fail_run(run, "ACCOUNT_NOT_FOUND: coa account missing")
            await self._session.commit()
            return {"status": "failed", "error": "ACCOUNT_NOT_FOUND"}

        rules_used: list[str] = []
        try:
            bank_items = await self._repo.list_unmatched_bank(run.id)
            ledger_items = await self._repo.list_unmatched_ledger(run.id)

            candidates = find_rule_based_matches(
                bank_items,
                ledger_items,
                amount_tolerance_pct=Decimal(
                    str(self._settings.reconciliation_amount_tolerance_pct)
                ),
            )
            for cand in candidates:
                await self._repo.record_auto_match(
                    run.id,
                    cand.bank_item_id,
                    cand.ledger_item_id,
                    confidence=cand.confidence,
                    match_reason=cand.match_reason,
                )
                if cand.rule_name not in rules_used:
                    rules_used.append(cand.rule_name)

            bank_items = await self._repo.list_unmatched_bank(run.id)
            ledger_items = await self._repo.list_unmatched_ledger(run.id)

            if bank_items and ledger_items:
                await self._apply_ai_matches(run.id, bank_items, ledger_items)

            await self._repo.complete_run(run, rules_used)
            await self._session.commit()

            if run.unmatched_count > 0:
                self._notify_review_needed(run)

            return {
                "status": "completed",
                "reconciliation_id": str(run.id),
                "matched_count": run.matched_count,
                "unmatched_count": run.unmatched_count,
                "match_rate": float(run.match_rate or 0),
            }
        except HermesError as exc:
            await self._repo.fail_run(run, f"{exc.error_code}: {exc}")
            await self._session.commit()
            return {"status": "failed", "error": exc.error_code}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Treasury reconciliation failed")
            await self._repo.fail_run(run, f"DB_WRITE_ERROR: {exc}")
            await self._session.commit()
            return {"status": "failed", "error": "DB_WRITE_ERROR"}

    async def _apply_ai_matches(self, run_id: UUID, bank_items, ledger_items) -> None:
        request = SuggestMatchesRequest(
            reconciliation_id=run_id,
            unmatched_bank_items=[
                HermesBankItem(
                    id=b.id,
                    transaction_date=b.transaction_date,
                    description=b.description,
                    reference=b.reference,
                    amount=str(b.amount),
                    currency=b.currency,
                )
                for b in bank_items
            ],
            unmatched_ledger_items=[
                HermesLedgerItem(
                    id=l.id,
                    transaction_date=l.transaction_date,
                    description=l.description,
                    reference=l.reference,
                    amount=str(l.amount),
                    currency=l.currency,
                )
                for l in ledger_items
            ],
            tolerance_amount_pct=self._settings.reconciliation_amount_tolerance_pct,
        )
        response = await self._hermes.suggest_matches(request)
        output = response.output
        if not output:
            return

        for suggestion in output.suggestions:
            conf = Decimal(str(suggestion.confidence))
            if conf >= Decimal("0.90"):
                await self._repo.record_auto_match(
                    run_id,
                    suggestion.bank_item_id,
                    suggestion.ledger_item_id,
                    confidence=conf,
                    match_reason="ai_suggested",
                )
            elif conf >= Decimal("0.80"):
                await self._repo.record_pending_ai_match(
                    run_id,
                    suggestion.bank_item_id,
                    suggestion.ledger_item_id,
                    confidence=conf,
                    match_reason="ai_suggested",
                )

    def _notify_review_needed(self, run) -> None:
        logger.info(
            "reconciliation_review reconciliation_id=%s unmatched=%s match_rate=%s",
            run.id,
            run.unmatched_count,
            run.match_rate,
        )
