"""Phase 4 integration: intake → case → accounts queue, case transitions."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.models.case import Case
from app.models.mail import Email
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.services.intake_processor import IntakeProcessor
from app.services.mail.intake_queue import enqueue_intake


@pytest.mark.integration
async def test_intake_creates_case_and_routes_to_accounts(db_session, auth_headers) -> None:
    email = Email(
        message_id=f"test-{uuid4()}@example.com",
        mailbox_address="ar@example.com",
        from_address="vendor@example.com",
        to_addresses=["ar@example.com"],
        cc_addresses=[],
        subject="Invoice 12345",
        body_preview="Please find attached invoice",
        status="queued",
        classified_as="ar_invoice",
        classification_confidence=0.92,
        received_at=datetime.now(UTC),
    )
    db_session.add(email)
    await db_session.commit()

    await enqueue_intake(email_id=email.id, mailbox=email.mailbox_address)

    processor = IntakeProcessor(db_session)
    raw = json.dumps({"email_id": str(email.id), "mailbox": email.mailbox_address})
    result = await processor.process_message(raw)
    assert result["status"] == "routed"
    assert "case_id" in result

    redis = get_redis()
    depth = await redis.llen(get_settings().accounts_queue_name)
    assert depth >= 1

    await db_session.refresh(email)
    assert email.case_id is not None
    assert email.case_number is not None


@pytest.mark.integration
async def test_case_status_transition_api(
    db_session, async_client: AsyncClient, auth_headers
) -> None:
    case = Case(
        case_number=f"CAS-TEST-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="classified",
        subject="Test case",
    )
    db_session.add(case)
    await db_session.flush()

    definition = WorkflowDefinition(
        name=f"test_ap_{uuid4().hex[:8]}",
        version=1,
        case_type="ap_invoice",
    )
    db_session.add(definition)
    await db_session.flush()

    instance = WorkflowInstance(
        case_id=case.id,
        definition_id=definition.id,
        current_state="classified",
    )
    db_session.add(instance)
    await db_session.commit()

    response = await async_client.post(
        f"/cases/{case.id}/status",
        headers=auth_headers,
        json={"trigger": "processing_started", "context": {}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["to_status"] == "processing"


@pytest.mark.integration
async def test_queue_status_endpoint(async_client: AsyncClient, auth_headers) -> None:
    response = await async_client.get("/workflow/queues", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "intake_queue" in data
    assert "accounts_queue" in data
    assert "dead_letter_queue" in data
