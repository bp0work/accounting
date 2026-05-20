"""Integration tests — Phase 11b executive email SOP."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mail_action_token import issue_escalation_token
from app.models.case import Case
from app.models.executive_mail import CaseEscalation
from app.models.mail import MailGatewayConfig
from app.services.finance_activity_log_service import FinanceActivityLogService
from app.schemas.executive_mail import FinanceActivityLogCreate

CRON_TOKEN = "test-cron-token-phase11b"


@pytest.fixture(autouse=True)
def _phase11b_env(monkeypatch):
    monkeypatch.setenv("FINANCE_INTERNAL_CRON__TOKEN", CRON_TOKEN)
    monkeypatch.setenv("FINANCE_MAIL_ACTION__SECRET", "test-mail-action-secret-phase11b")
    monkeypatch.setenv("FINANCE_HASH_SECRET", "test-hash-secret-phase11b-32bytes!!")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.mark.integration
async def test_finance_daily_log_requires_cron_token(async_client: AsyncClient):
    response = await async_client.post("/internal/jobs/finance-daily-log")
    assert response.status_code == 401


@pytest.mark.integration
async def test_finance_daily_log_sent_and_idempotent(
    async_client: AsyncClient, db_session: AsyncSession
):
    log_svc = FinanceActivityLogService(db_session)
    await log_svc.log(
        FinanceActivityLogCreate(
            actor_type="system",
            action="test_digest",
            summary="pytest finance activity row",
        )
    )
    await db_session.commit()

    headers = {"Authorization": f"Bearer {CRON_TOKEN}"}
    first = await async_client.post(
        "/internal/jobs/finance-daily-log",
        headers=headers,
        json={"force": True},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "sent"
    assert body["row_count"] >= 1
    assert body["attachment_filename"].startswith("finance_daily_")

    second = await async_client.post("/internal/jobs/finance-daily-log", headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "skipped"
    assert second.json()["reason"] == "already_sent"


@pytest.mark.integration
async def test_escalation_respond_approve(async_client: AsyncClient, db_session: AsyncSession):
    mailbox = (
        await db_session.execute(select(MailGatewayConfig).limit(1))
    ).scalar_one()

    case = Case(
        id=uuid.uuid4(),
        case_number=f"CAS-PYTEST-{uuid.uuid4().hex[:8]}",
        type="general_inquiry",
        status="on_hold",
        subject="pytest escalation case",
    )
    db_session.add(case)
    await db_session.flush()

    esc_id = uuid.uuid4()
    wire, token_hash, expires = issue_escalation_token(escalation_id=esc_id, case_id=case.id)
    escalation = CaseEscalation(
        id=esc_id,
        case_id=case.id,
        originating_mailbox_id=mailbox.id,
        target_email=mailbox.email_address,
        summary="pytest escalation",
        response_token_hash=token_hash,
        token_expires_at=expires,
    )
    db_session.add(escalation)
    await db_session.commit()

    response = await async_client.get(
        f"/mail/escalations/{esc_id}/respond",
        params={"action": "approve", "token": wire},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "approve"
    assert data["status"] == "approved"
