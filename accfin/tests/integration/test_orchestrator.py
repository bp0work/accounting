"""Phase 4/5 integration: accounts classification, case transitions, queues."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from agents.hermes.classify import classify_email_stub
from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.models.case import Case
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.schemas.hermes import ClassifyEmailRequest, ClassifyEmailResponse
from app.services.mail.intake_queue import enqueue_intake
from app.models.mail import Email
from workers.accounts.classification import ClassificationService, GeneralInquiryHandler


class _StubHermes:
    """Rule-based classifier without HTTP."""

    async def classify_email(self, request: ClassifyEmailRequest) -> ClassifyEmailResponse:
        return classify_email_stub(request)


@pytest.mark.integration
async def test_intake_creates_case_and_routes_to_accounts(db_session) -> None:
    email = Email(
        message_id=f"test-{uuid4()}@example.com",
        mailbox_address="accap.mmlogistix@bp0.work",
        from_address="vendor@example.com",
        to_addresses=["accap.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject="Invoice INV-99001 for May 2026",
        body_preview="Please find attached our invoice",
        status="queued",
        received_at=datetime.now(UTC),
    )
    db_session.add(email)
    await db_session.commit()

    await enqueue_intake(email_id=email.id, mailbox=email.mailbox_address)

    service = ClassificationService(db_session, hermes=_StubHermes())
    raw = json.dumps({"message_id": str(uuid4()), "email_id": str(email.id), "mailbox": email.mailbox_address})
    result = await service.process_intake(raw)
    await db_session.commit()

    assert result["status"] == "routed"
    assert "case_id" in result

    redis = get_redis()
    depth = await redis.llen(get_settings().accounts_queue_name)
    assert depth >= 1

    await db_session.refresh(email)
    assert email.case_id is not None
    assert email.classified_as is not None


@pytest.mark.integration
async def test_general_inquiry_manual_review(db_session) -> None:
    case = Case(
        case_number=f"CAS-GI-{uuid4().hex[:8]}",
        type="general_inquiry",
        status="classified",
        subject="General question",
    )
    db_session.add(case)
    await db_session.commit()

    message = {
        "message_id": str(uuid4()),
        "case_id": str(case.id),
        "case_type": "general_inquiry",
    }
    result = await GeneralInquiryHandler(db_session).process(message)
    await db_session.commit()
    assert result["status"] == "manual_review"
    await db_session.refresh(case)
    assert case.status == "manual_review"


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
        f"/api/cases/{case.id}/status",
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
