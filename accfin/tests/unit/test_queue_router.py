"""Queue routing helpers."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.case import Case
from app.services.queue_router import enqueue_accounts, route_case_to_queue


@pytest.mark.asyncio
async def test_route_case_to_queue_pushes_accounts_payload():
    case = Case(
        id=uuid.uuid4(),
        case_number="CAS-TEST-0001",
        type="ap_invoice",
        status="classified",
        priority="high",
        stp_eligible=True,
        confidence_score=Decimal("0.95"),
        email_id=uuid.uuid4(),
    )

    with patch(
        "app.services.queue_router.enqueue_accounts",
        new=AsyncMock(return_value="msg-123"),
    ) as mock_enqueue:
        message_id = await route_case_to_queue(
            case=case,
            session=None,
            confidence_score=0.95,
        )

    assert message_id == "msg-123"
    mock_enqueue.assert_awaited_once_with(
        case_id=case.id,
        case_type="ap_invoice",
        case_number="CAS-TEST-0001",
        email_id=case.email_id,
        priority="high",
        stp_eligible=True,
        confidence_score=0.95,
        source="accounts-worker",
    )


@pytest.mark.asyncio
async def test_enqueue_accounts_includes_override_policy_when_set():
    case_id = uuid.uuid4()
    redis = AsyncMock()
    redis.rpush = AsyncMock()

    with (
        patch("app.services.queue_router.get_redis", return_value=redis),
        patch("app.services.queue_router.get_settings") as mock_settings,
    ):
        mock_settings.return_value.accounts_queue_name = "accounts_queue"
        await enqueue_accounts(
            case_id=case_id,
            case_type="expense_claim",
            case_number="CAS-EXP-0001",
            override_policy=True,
        )

    redis.rpush.assert_awaited_once()
    payload = json.loads(redis.rpush.await_args.args[1])
    assert payload["override_policy"] is True
    assert payload["case_id"] == str(case_id)


@pytest.mark.asyncio
async def test_enqueue_accounts_includes_override_receipt_and_kwargs():
    case_id = uuid.uuid4()
    redis = AsyncMock()
    redis.rpush = AsyncMock()

    with (
        patch("app.services.queue_router.get_redis", return_value=redis),
        patch("app.services.queue_router.get_settings") as mock_settings,
    ):
        mock_settings.return_value.accounts_queue_name = "accounts_queue"
        await enqueue_accounts(
            case_id=case_id,
            case_type="expense_claim",
            case_number="CAS-EXP-0002",
            override_receipt=True,
            override_parsing=True,
        )

    payload = json.loads(redis.rpush.await_args.args[1])
    assert payload["override_receipt"] is True
    assert payload["override_parsing"] is True
