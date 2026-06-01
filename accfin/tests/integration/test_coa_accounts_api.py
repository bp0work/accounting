"""COA accounts API for Finance UI expense parsing — `0.14.50`."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import CoaAccount
from tests.conftest import TEST_PASSWORD


@pytest.mark.integration
async def test_list_coa_accounts_filters_expense_type(
    async_client: AsyncClient,
    accounts_manager_user,
    db_session: AsyncSession,
):
    db_session.add(
        CoaAccount(
            account_code="6100",
            account_name="Travel",
            account_type="expense",
            account_subtype="travel",
        )
    )
    db_session.add(
        CoaAccount(
            account_code="1200",
            account_name="Bank",
            account_type="asset",
        )
    )
    await db_session.commit()

    login = await async_client.post(
        "/api/auth/login",
        json={"username": accounts_manager_user.username, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]
    response = await async_client.get(
        "/api/coa-accounts?account_type=expense",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    rows = response.json()
    codes = {row["account_code"] for row in rows}
    assert "6100" in codes
    assert "1200" not in codes
    travel = next(row for row in rows if row["account_code"] == "6100")
    assert travel["account_subtype"] == "travel"
