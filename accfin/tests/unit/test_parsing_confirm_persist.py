"""Parsing confirmation — metadata persist and queue payload."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.case import Case
from app.services.queue_router import enqueue_accounts
from workers.common.parsing_confirmation import (
    apply_confirmed_extracted_fields_from_message,
    normalize_extracted_fields,
)


def test_apply_confirmed_extracted_fields_from_message_updates_case() -> None:
    case = Case(
        id=uuid.uuid4(),
        case_number="CAS-EXP-0001",
        type="expense_claim",
        status="classified",
        subject="test",
        workflow_metadata={"extracted_fields": {"vendor_name": "Old"}},
    )
    confirmed = normalize_extracted_fields(
        {
            "document_type": "receipt",
            "vendor_name": "New Cafe",
            "total_amount": "42.00",
            "currency": "SGD",
            "document_date": "2026-05-01",
            "gl_account_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        }
    )
    message = {"parsing_confirmed": True, "confirmed_extracted_fields": confirmed}

    out = apply_confirmed_extracted_fields_from_message(case, message)

    assert out is not None
    assert case.workflow_metadata["extracted_fields"]["vendor_name"] == "New Cafe"
    assert (
        case.workflow_metadata["extracted_fields"]["gl_account_id"]
        == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    )


@pytest.mark.asyncio
async def test_enqueue_accounts_includes_confirmed_extracted_fields() -> None:
    case_id = uuid.uuid4()
    fields = normalize_extracted_fields(
        {
            "document_type": "receipt",
            "vendor_name": "Cafe",
            "total_amount": "10.00",
            "currency": "SGD",
            "document_date": "2026-05-01",
        }
    )
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
            parsing_confirmed=True,
            confirmed_extracted_fields=fields,
        )

    import json

    payload = json.loads(redis.rpush.await_args.args[1])
    assert payload["parsing_confirmed"] is True
    assert payload["confirmed_extracted_fields"]["vendor_name"] == "Cafe"
