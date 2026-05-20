"""Phase 8 Treasury Worker integration tests."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from agents.hermes.reconcile import suggest_matches_stub
from app.models.ledger import CoaAccount
from app.models.reconciliation import ReconciliationLedgerItem, ReconciliationRun
from app.repositories.reconciliation import ReconciliationRepository
from app.schemas.hermes import SuggestMatchesRequest, SuggestMatchesResponse
from workers.treasury.worker import TreasuryWorker


class _StubHermes:
    async def suggest_matches(self, request: SuggestMatchesRequest) -> SuggestMatchesResponse:
        return suggest_matches_stub(request)


@pytest.mark.integration
async def test_treasury_reconciliation_full_round_trip(db_session, test_user) -> None:
    result = await db_session.execute(
        select(CoaAccount).where(CoaAccount.account_code == "1200")
    )
    account = result.scalar_one_or_none()
    if account is None:
        pytest.skip("Bank account 1200 not seeded")

    repo = ReconciliationRepository(db_session)
    period_from = date(2026, 4, 1)
    period_to = date(2026, 4, 30)
    run = await repo.create_run(
        account_id=account.id,
        period_from=period_from,
        period_to=period_to,
        started_by=test_user.id,
        opening_balance=Decimal("1000.00"),
    )
    tx_date = date(2026, 4, 15)
    await repo.add_bank_items(
        run.id,
        [
            {
                "transaction_date": tx_date,
                "reference": "TT-100",
                "amount": "500.00",
                "description": "Customer receipt",
            },
            {
                "transaction_date": tx_date,
                "reference": "TT-999",
                "amount": "25.00",
                "description": "Unmatched fee",
            },
        ],
    )
    db_session.add(
        ReconciliationLedgerItem(
            reconciliation_run_id=run.id,
            transaction_date=tx_date,
            reference="TT-100",
            amount=Decimal("500.00"),
            description="Ledger receipt",
            currency="SGD",
        )
    )
    await repo.set_run_totals(run)
    await db_session.commit()

    worker = TreasuryWorker(db_session, hermes=_StubHermes())
    outcome = await worker.run_reconciliation(run.id)
    await db_session.commit()
    await db_session.refresh(run)

    assert outcome["status"] == "completed"
    assert run.status == "completed"
    assert run.matched_count >= 1
    assert run.match_rate is not None


@pytest.mark.integration
async def test_treasury_idempotency_completed(db_session, test_user) -> None:
    result = await db_session.execute(
        select(CoaAccount).where(CoaAccount.account_code == "1200")
    )
    account = result.scalar_one_or_none()
    if account is None:
        pytest.skip("Bank account 1200 not seeded")

    run = ReconciliationRun(
        account_id=account.id,
        statement_period_from=date(2026, 3, 1),
        statement_period_to=date(2026, 3, 31),
        started_by=test_user.id,
        status="completed",
        total_bank_transactions=0,
        total_ledger_transactions=0,
        matched_count=0,
    )
    db_session.add(run)
    await db_session.commit()

    worker = TreasuryWorker(db_session, hermes=_StubHermes())
    outcome = await worker.run_reconciliation(run.id)
    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "already_completed"


@pytest.mark.integration
async def test_treasury_idempotency_in_progress(db_session, test_user) -> None:
    result = await db_session.execute(
        select(CoaAccount).where(CoaAccount.account_code == "1200")
    )
    account = result.scalar_one_or_none()
    if account is None:
        pytest.skip("Bank account 1200 not seeded")

    from datetime import UTC, datetime

    run = ReconciliationRun(
        account_id=account.id,
        statement_period_from=date(2026, 2, 1),
        statement_period_to=date(2026, 2, 28),
        started_by=test_user.id,
        status="in_progress",
        started_at=datetime.now(UTC) - timedelta(minutes=3),
        total_bank_transactions=1,
        total_ledger_transactions=0,
        match_rules_used=["exact_amount_date_reference"],
    )
    db_session.add(run)
    await db_session.commit()

    worker = TreasuryWorker(db_session, hermes=_StubHermes())
    outcome = await worker.run_reconciliation(run.id)
    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "already_in_progress"
