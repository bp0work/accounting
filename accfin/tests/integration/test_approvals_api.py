"""Phase 9 Approvals API integration tests."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.case import Case, Counterparty
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.services.approval_service import ApprovalService
from tests.conftest import TEST_PASSWORD


@pytest.mark.integration
async def test_approvals_list_and_approve(
    async_client: AsyncClient, db_session, test_user, auth_headers
) -> None:
    cp = Counterparty(name=f"Approval CP {uuid4().hex[:6]}", type="supplier")
    db_session.add(cp)
    await db_session.flush()

    case = Case(
        case_number=f"CAS-APR-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="pending_approval",
        subject="Invoice pending approval",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
        amount_value=Decimal("1500.00"),
        amount_currency="SGD",
    )
    db_session.add(case)
    await db_session.flush()

    wf = WorkflowDefinition(name=f"wf_apr_{uuid4().hex[:8]}", version=1, case_type="ap_invoice")
    db_session.add(wf)
    await db_session.flush()
    db_session.add(
        WorkflowInstance(case_id=case.id, definition_id=wf.id, current_state="pending_approval")
    )
    await db_session.flush()

    service = ApprovalService(db_session)
    approval = await service.request_approval(
        case_id=case.id,
        tier=2,
        amount_value=Decimal("1500.00"),
        approver_id=test_user.id,
    )
    await db_session.commit()

    listed = await async_client.get(
        "/api/approvals?my_pending=true", headers=auth_headers
    )
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert any(row["id"] == str(approval.id) for row in data)

    approved = await async_client.post(
        f"/api/approvals/{approval.id}/approve",
        headers=auth_headers,
        json={"note": "Verified — approved in test"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    await db_session.refresh(case)
    assert case.status in ("approved", "posted", "completed")


@pytest.mark.integration
async def test_approvals_reject(
    async_client: AsyncClient, db_session, test_user, auth_headers
) -> None:
    case = Case(
        case_number=f"CAS-REJ-{uuid4().hex[:8]}",
        type="ar_invoice",
        status="pending_approval",
        subject="Reject me",
    )
    db_session.add(case)
    await db_session.flush()

    service = ApprovalService(db_session)
    approval = await service.request_approval(
        case_id=case.id, tier=1, approver_id=test_user.id
    )
    await db_session.commit()

    resp = await async_client.post(
        f"/api/approvals/{approval.id}/reject",
        headers=auth_headers,
        json={"reason": "Insufficient documentation", "rejection_category": "other"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.integration
async def test_notification_preferences_roundtrip(
    async_client: AsyncClient, auth_headers
) -> None:
    templates = await async_client.get("/api/notification-templates", headers=auth_headers)
    assert templates.status_code == 200
    assert len(templates.json()) >= 1

    updated = await async_client.put(
        "/api/users/me/notification-preferences",
        headers=auth_headers,
        json={
            "quiet_hours": {"enabled": False},
            "channels": {"email": True, "in_app": True},
            "subscriptions": [
                {"event_key": "approval.requested", "email": True, "in_app": True, "digest": "off"}
            ],
        },
    )
    assert updated.status_code == 200

    inbox = await async_client.get("/notifications", headers=auth_headers)
    assert inbox.status_code == 200
    assert "unread_count" in inbox.json()
