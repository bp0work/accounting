"""Queue routing helpers."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.case import Case
from app.services.queue_router import route_case_to_queue


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
