"""Vendor suggestions API integration tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case, Counterparty

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_vendor_suggestions_endpoint_returns_200(
    async_client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
) -> None:
    suffix = uuid.uuid4().hex[:8]
    counterparty = Counterparty(
        id=uuid.uuid4(),
        name=f"Suggest Vendor {suffix}",
        type="employee",
        contact_email=f"vendor_{suffix}@example.com",
    )
    db_session.add(counterparty)
    case = Case(
        id=uuid.uuid4(),
        case_number=f"EC-SUG-{suffix}",
        type="expense_claim",
        status="posted",
        subject="Posted expense for suggestions",
        workflow_metadata={
            "extracted_fields": {"vendor_name": f"History Vendor {suffix}"},
        },
    )
    db_session.add(case)
    await db_session.commit()

    short = await async_client.get(
        "/api/vendor-suggestions",
        params={"search": "S"},
        headers=auth_headers,
    )
    assert short.status_code == 422

    response = await async_client.get(
        "/api/vendor-suggestions",
        params={"search": "Suggest", "limit": 10},
        headers=auth_headers,
    )
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    names = {row["name"] for row in rows}
    assert f"Suggest Vendor {suffix}" in names
    assert f"History Vendor {suffix}" in names
    counterparty_row = next(row for row in rows if row["name"] == f"Suggest Vendor {suffix}")
    assert counterparty_row["source"] == "counterparty"
    assert counterparty_row["counterparty_type"] == "employee"
    history_row = next(row for row in rows if row["name"] == f"History Vendor {suffix}")
    assert history_row["source"] == "case_history"
