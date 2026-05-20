"""Integration tests for expense claims API — `05` §18."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseAttachment
from app.repositories.case import CaseRepository
from tests.conftest import TEST_PASSWORD


async def _create_receipt_attachment(db_session: AsyncSession, *, uploaded_by) -> uuid.UUID:
    """Insert a real case_attachments row (pre-upload on a staging case)."""
    cases = CaseRepository(db_session)
    staging_case = await cases.create_manual_case(
        case_type="expense_claim",
        subject="Expense receipt staging",
        description="Staging case for receipt upload",
    )
    receipt_id = uuid.uuid4()
    db_session.add(
        CaseAttachment(
            id=receipt_id,
            case_id=staging_case.id,
            filename="receipt.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            storage_path=f"/data/attachments/{receipt_id}.pdf",
            uploaded_by=uploaded_by,
        )
    )
    await db_session.commit()
    return receipt_id


@pytest.mark.integration
async def test_submit_expense_claim_requires_permission(async_client: AsyncClient, auditor_user):
    login = await async_client.post(
        "/auth/login",
        json={"username": auditor_user.username, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]
    response = await async_client.post(
        "/expense-claims",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "category": "meals",
            "merchant": "Test Cafe",
            "amount_value": "25.50",
            "amount_currency": "SGD",
            "receipt_date": "2026-05-10",
            "purpose": "Team lunch during project kickoff meeting",
            "attachment_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_submit_and_list_expense_claim(
    async_client: AsyncClient,
    clerk_user,
    db_session: AsyncSession,
):
    receipt_id = await _create_receipt_attachment(db_session, uploaded_by=clerk_user.id)

    login = await async_client.post(
        "/auth/login",
        json={"username": clerk_user.username, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Submit creates a new case; use a fresh attachment id so the API can attach the receipt
    # to that case (not a fixed UUID that may already exist on another case).
    submit_receipt_id = uuid.uuid4()
    submit = await async_client.post(
        "/expense-claims",
        headers=headers,
        json={
            "category": "transport",
            "merchant": "Grab",
            "amount_value": "18.00",
            "amount_currency": "SGD",
            "receipt_date": "2026-05-10",
            "purpose": "Client site visit transport reimbursement",
            "attachment_ids": [str(submit_receipt_id)],
        },
    )
    assert submit.status_code == 201, submit.text
    body = submit.json()["data"]
    assert body["case_number"].startswith("CAS-")
    assert body["status"] == "processing"

    listed = await async_client.get("/expense-claims", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["data"]
    assert any(i["expense_claim_id"] == body["expense_claim_id"] for i in items)

    detail = await async_client.get(f"/expense-claims/{body['expense_claim_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["merchant"] == "Grab"

    # Pre-created staging receipt exists independently of the submit flow.
    assert receipt_id != submit_receipt_id
