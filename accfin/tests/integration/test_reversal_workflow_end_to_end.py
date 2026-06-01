"""Expense reversal workflow integration test."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.case import Case
from app.models.ledger import CoaAccount, JournalEntry, JournalEntryLine
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.integration


async def _login(client: AsyncClient, username: str, password: str = TEST_PASSWORD) -> dict[str, str]:
    response = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _posted_expense(
    db_session,
) -> Case:
    expense = CoaAccount(
        account_code=f"6{uuid4().hex[:4]}",
        account_name="Meals",
        account_type="expense",
        is_active=True,
    )
    payable = CoaAccount(
        account_code=f"2{uuid4().hex[:4]}",
        account_name="Payable",
        account_type="liability",
        is_active=True,
    )
    db_session.add_all([expense, payable])
    await db_session.flush()
    case = Case(
        case_number=f"CAS-E2E-{uuid4().hex[:6]}",
        type="expense_claim",
        status="case_closed",
        subject="E2E reversal",
        amount_value=Decimal("50.00"),
        amount_currency="SGD",
    )
    db_session.add(case)
    await db_session.flush()
    entry = JournalEntry(
        entry_number=f"JE-{uuid4().hex[:8]}",
        case_id=case.id,
        case_number=case.case_number,
        status="posted",
        entry_date=case.created_at.date(),
        description="Posted",
        currency="SGD",
        total_debit=Decimal("50"),
        total_credit=Decimal("50"),
        is_balanced=True,
    )
    db_session.add(entry)
    await db_session.flush()
    db_session.add_all(
        [
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_number=1,
                account_id=expense.id,
                debit=Decimal("50"),
                credit=Decimal("0"),
            ),
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_number=2,
                account_id=payable.id,
                debit=Decimal("0"),
                credit=Decimal("50"),
            ),
        ]
    )
    await db_session.commit()
    return case


@pytest.mark.asyncio
async def test_reversal_workflow_end_to_end(
    async_client: AsyncClient,
    db_session,
    accounts_manager_user,
) -> None:
    case = await _posted_expense(db_session)
    acc_headers = await _login(async_client, accounts_manager_user.username)

    raise_res = await async_client.post(
        f"/api/cases/{case.id}/raise-reversal",
        headers=acc_headers,
        json={"reason": "Duplicate"},
    )
    assert raise_res.status_code == 200, raise_res.text
    reversal_id = raise_res.json()["reversal_case_id"]

    detail = await async_client.get(f"/api/cases/{reversal_id}", headers=acc_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "pending_reversal_approval"
    assert body["parent_case_number"] == case.case_number
    assert body["journal_entry"] is not None

    # CFO login via seeded user if available — use approvals:admin permission on test user path:
    # finance officer won't work; skip if no cfo in DB
    from app.models.rbac import Role
    from app.models.user import User
    from app.core.security.password import hash_password

    cfo_role = await db_session.scalar(select(Role).where(Role.name == "cfo"))
    if cfo_role is None:
        pytest.skip("CFO role not seeded")
    cfo = User(
        id=uuid4(),
        username=f"cfo_e2e_{uuid4().hex[:6]}",
        display_name="CFO E2E",
        email=f"cfo_e2e_{uuid4().hex[:6]}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=cfo_role.id,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(cfo)
    await db_session.commit()
    cfo_headers = await _login(async_client, cfo.username)

    approve_res = await async_client.post(
        f"/api/cases/{reversal_id}/approve-reversal",
        headers=cfo_headers,
        json={"comment": "Approved"},
    )
    assert approve_res.status_code == 200, approve_res.text
    assert approve_res.json()["status"] == "reversed"

    original_res = await async_client.get(f"/api/cases/{case.id}", headers=acc_headers)
    assert original_res.status_code == 200
    assert original_res.json()["workflow_metadata"].get("reversed_by")

    je_result = await db_session.execute(
        select(JournalEntry)
        .where(JournalEntry.case_id == reversal_id)
        .options(selectinload(JournalEntry.lines))
    )
    posted_reversal = je_result.scalar_one()
    assert posted_reversal.status == "posted"
