"""Finance UI — POST /api/cases/{id}/escalation-respond."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.mail_action_token import issue_escalation_token
from app.models.case import Case
from app.models.executive_mail import CaseEscalation
from app.models.mail import MailGatewayConfig


@pytest.fixture
async def clerk_auth_headers(async_client: AsyncClient, accounts_manager_user) -> dict[str, str]:
    response = await async_client.post(
        "/api/auth/login",
        json={"username": accounts_manager_user.username, "password": "CorrectHorseBattery1!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
async def test_case_escalation_respond_approve(
    db_session, async_client: AsyncClient, clerk_auth_headers: dict[str, str]
) -> None:
    mailbox = (await db_session.execute(select(MailGatewayConfig).limit(1))).scalar_one()

    case = Case(
        id=uuid4(),
        case_number=f"CAS-UI-ESC-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="on_hold",
        subject="pytest UI escalation",
        workflow_metadata={"escalation_pending": True, "reason_code": "AP_CONTRACT_MISSING"},
    )
    db_session.add(case)
    await db_session.flush()

    esc_id = uuid4()
    wire, token_hash, expires = issue_escalation_token(escalation_id=esc_id, case_id=case.id)
    escalation = CaseEscalation(
        id=esc_id,
        case_id=case.id,
        originating_mailbox_id=mailbox.id,
        target_email=mailbox.email_address,
        status="pending",
        reason_code="AP_CONTRACT_MISSING",
        summary="Contract missing",
        context={"notification": {"wire_token": wire}},
        response_token_hash=token_hash,
        token_expires_at=expires,
    )
    db_session.add(escalation)
    meta = dict(case.workflow_metadata or {})
    meta["escalation_id"] = str(esc_id)
    case.workflow_metadata = meta
    await db_session.commit()

    response = await async_client.post(
        f"/api/cases/{case.id}/escalation-respond",
        headers=clerk_auth_headers,
        json={"action": "approve", "comment": "Contract updated in counterparty setup"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["action"] == "approve"
    assert data["status"] == "approved"


@pytest.mark.integration
async def test_case_escalation_respond_forbidden_for_auditor(
    db_session, async_client: AsyncClient, auditor_auth_headers: dict[str, str]
) -> None:
    case = Case(
        case_number=f"CAS-UI-DENY-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="manual_review",
    )
    db_session.add(case)
    await db_session.commit()

    response = await async_client.post(
        f"/api/cases/{case.id}/escalation-respond",
        headers=auditor_auth_headers,
        json={"action": "reject", "comment": "n/a"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_case_escalation_respond_retry(
    db_session, async_client: AsyncClient, clerk_auth_headers: dict[str, str]
) -> None:
    mailbox = (await db_session.execute(select(MailGatewayConfig).limit(1))).scalar_one()

    case = Case(
        id=uuid4(),
        case_number=f"CAS-UI-RETRY-{uuid4().hex[:8]}",
        type="expense_claim",
        status="manual_review",
        subject="pytest escalation retry",
        workflow_metadata={
            "escalation_pending": True,
            "reason_code": "EXP_SUBMITTER_NOT_FOUND",
            "resume_from_step": "2C",
        },
    )
    db_session.add(case)
    await db_session.flush()

    esc_id = uuid4()
    wire, token_hash, expires = issue_escalation_token(escalation_id=esc_id, case_id=case.id)
    escalation = CaseEscalation(
        id=esc_id,
        case_id=case.id,
        originating_mailbox_id=mailbox.id,
        target_email=mailbox.email_address,
        status="pending",
        reason_code="EXP_SUBMITTER_NOT_FOUND",
        summary="Submitter not found",
        context={"notification": {"wire_token": wire}},
        response_token_hash=token_hash,
        token_expires_at=expires,
    )
    db_session.add(escalation)
    meta = dict(case.workflow_metadata or {})
    meta["escalation_id"] = str(esc_id)
    case.workflow_metadata = meta
    await db_session.commit()

    response = await async_client.post(
        f"/api/cases/{case.id}/escalation-respond",
        headers=clerk_auth_headers,
        json={"action": "retry", "comment": "Employee counterparty added"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["action"] == "retry"
    assert data["status"] == "approved"

    await db_session.refresh(case)
    await db_session.refresh(escalation)
    assert escalation.status == "approved"
    assert case.status == "classified"
    assert case.workflow_metadata.get("escalation_pending") is False
    assert case.workflow_metadata.get("resume_from_step") == "2C"
    assert case.workflow_metadata.get("manual_retry") is True


@pytest.mark.integration
async def test_case_escalation_respond_retry_exp_parsing_incomplete_on_hold(
    db_session, async_client: AsyncClient, clerk_auth_headers: dict[str, str]
) -> None:
    """EXP_PARSING_INCOMPLETE stays on_hold — Finance UI must use escalation-respond, not /retry."""
    mailbox = (await db_session.execute(select(MailGatewayConfig).limit(1))).scalar_one()

    case = Case(
        id=uuid4(),
        case_number=f"CAS-UI-PARSE-{uuid4().hex[:8]}",
        type="expense_claim",
        status="on_hold",
        subject="pytest parsing incomplete",
        workflow_metadata={
            "escalation_pending": True,
            "reason_code": "EXP_PARSING_INCOMPLETE",
            "missing_fields": ["document_date"],
            "resume_from_step": "2A",
        },
    )
    db_session.add(case)
    await db_session.flush()

    esc_id = uuid4()
    wire, token_hash, expires = issue_escalation_token(escalation_id=esc_id, case_id=case.id)
    escalation = CaseEscalation(
        id=esc_id,
        case_id=case.id,
        originating_mailbox_id=mailbox.id,
        target_email=mailbox.email_address,
        status="pending",
        reason_code="EXP_PARSING_INCOMPLETE",
        summary="Parsing incomplete",
        context={"notification": {"wire_token": wire}},
        response_token_hash=token_hash,
        token_expires_at=expires,
    )
    db_session.add(escalation)
    meta = dict(case.workflow_metadata or {})
    meta["escalation_id"] = str(esc_id)
    case.workflow_metadata = meta
    await db_session.commit()

    retry_direct = await async_client.post(
        f"/api/cases/{case.id}/retry",
        headers=clerk_auth_headers,
    )
    assert retry_direct.status_code == 422
    assert retry_direct.json()["error"]["code"] == "CASE_NOT_RETRYABLE"

    response = await async_client.post(
        f"/api/cases/{case.id}/escalation-respond",
        headers=clerk_auth_headers,
        json={"action": "retry", "comment": "Vendor hint saved"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["action"] == "retry"

    await db_session.refresh(case)
    assert case.status == "classified"
    assert case.workflow_metadata.get("manual_retry") is True
    assert case.workflow_metadata.get("resume_from_step") == "2A"
