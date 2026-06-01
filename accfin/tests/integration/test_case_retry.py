"""Case manual retry — requeue exception/manual_review to accounts_queue."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.models.case import Case


@pytest.mark.integration
async def test_case_retry_requeues_manual_review(
    db_session, async_client: AsyncClient, auth_headers
) -> None:
    case = Case(
        case_number=f"CAS-RETRY-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="manual_review",
        subject="Hermes timeout retry test",
        workflow_metadata={
            "error_type": "HERMES_TIMEOUT",
            "error_message": "Read timed out",
            "current_stage": "processing",
        },
    )
    db_session.add(case)
    await db_session.commit()

    redis = get_redis()
    settings = get_settings()
    before = await redis.llen(settings.accounts_queue_name)

    response = await async_client.post(
        f"/api/cases/{case.id}/retry",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["previous_status"] == "manual_review"
    assert body["status"] == "classified"
    assert body["case_number"] == case.case_number
    assert body["message_id"]

    after = await redis.llen(settings.accounts_queue_name)
    assert after == before + 1

    await db_session.refresh(case)
    assert case.status == "classified"
    assert case.workflow_metadata.get("manual_retry") is True
    assert "error_message" not in case.workflow_metadata


@pytest.mark.integration
async def test_case_retry_requeues_on_hold_hermes_timeout(
    db_session, async_client: AsyncClient, auth_headers
) -> None:
    """Escalated AP failures keep reason_code on_hold — retry must still work."""
    case = Case(
        case_number=f"CAS-HERMES-HOLD-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="on_hold",
        subject="Hermes timeout on hold",
        workflow_metadata={
            "current_stage": "classification",
            "reason_code": "HERMES_TIMEOUT",
            "error_code": "HERMES_TIMEOUT",
            "error_reason": "Worker processing error — HERMES_TIMEOUT: Read timed out",
            "escalation_pending": True,
        },
    )
    db_session.add(case)
    await db_session.commit()

    response = await async_client.post(
        f"/api/cases/{case.id}/retry",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["previous_status"] == "on_hold"
    assert body["status"] == "classified"

    await db_session.refresh(case)
    assert case.status == "classified"
    assert case.workflow_metadata.get("manual_retry") is True
    assert "reason_code" not in case.workflow_metadata
    assert "error_code" not in case.workflow_metadata


@pytest.mark.integration
async def test_case_retry_requeues_classified(
    db_session, async_client: AsyncClient, auth_headers
) -> None:
    case = Case(
        case_number=f"CAS-RETRY-CLS-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="classified",
        subject="Stuck after classify",
        workflow_metadata={"current_stage": "processing"},
    )
    db_session.add(case)
    await db_session.commit()

    redis = get_redis()
    settings = get_settings()
    before = await redis.llen(settings.accounts_queue_name)

    response = await async_client.post(
        f"/api/cases/{case.id}/retry",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["previous_status"] == "classified"
    assert body["status"] == "classified"

    after = await redis.llen(settings.accounts_queue_name)
    assert after == before + 1


@pytest.mark.integration
async def test_case_retry_rejects_non_retryable_status(
    db_session, async_client: AsyncClient, auth_headers
) -> None:
    case = Case(
        case_number=f"CAS-NORETRY-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="posted",
        subject="Already posted",
    )
    db_session.add(case)
    await db_session.commit()

    response = await async_client.post(
        f"/api/cases/{case.id}/retry",
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CASE_NOT_RETRYABLE"
