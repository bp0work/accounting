"""Unit tests — mail deduplication."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import uuid

from app.services.mail.dedup import EmailDedupService


@pytest.mark.asyncio
async def test_dedup_blocks_same_message_id():
    session = AsyncMock()
    existing = MagicMock()
    existing.id = uuid.uuid4()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    session.execute.return_value = result_mock

    svc = EmailDedupService(session)
    out = await svc.check(message_id="<same@id>", content_hash="abc123")

    assert out.is_duplicate is True
    assert out.reason == "message_id"
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_dedup_allows_same_content_different_message_id():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    svc = EmailDedupService(session)
    out = await svc.check(message_id="<new@id>", content_hash="same-hash")

    assert out.is_duplicate is False
    assert session.execute.await_count == 1
