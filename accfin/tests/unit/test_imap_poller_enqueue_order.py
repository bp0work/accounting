"""IMAP poller — intake Redis enqueue must follow DB commit."""

from __future__ import annotations

from uuid import uuid4

import pytest

from gateway.imap import poller as poller_module
from gateway.imap.poller import _poll_mailbox_in_session


@pytest.mark.asyncio
async def test_poll_mailbox_commits_before_intake_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis push runs only after session.commit() for the poll transaction."""
    order: list[str] = []
    mailbox_id = uuid4()
    email_id = uuid4()

    class FakeSession:
        async def commit(self) -> None:
            order.append("commit")

    async def fake_enqueue_after_commit(_factory, _pending) -> None:
        order.append("redis")

    monkeypatch.setattr(poller_module, "_enqueue_intake_after_commit", fake_enqueue_after_commit)
    async def fake_to_thread(fn, *a):
        return [b"raw"]

    monkeypatch.setattr(poller_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(poller_module, "parse_rfc822", lambda raw, mailbox_address: object())
    monkeypatch.setattr(poller_module, "_imap_settings_from", lambda m: object())

    class FakeIngest:
        def __init__(self, _session):
            pass

        async def ingest(self, *, mailbox, parsed):
            order.append("ingest")

            class E:
                id = email_id
                linked_case_id = None
                status = "parsed"
                subject = "Test"

            return E()

    monkeypatch.setattr(poller_module, "MailIngestService", FakeIngest)

    class FakeRepo:
        def __init__(self, _session):
            pass

        async def get_mailbox_by_id(self, _id):
            class M:
                email_address = "accap@example.com"
                last_poll_at = None
                last_error = None
                error_count = 0

            return M()

    monkeypatch.setattr(poller_module, "MailRepository", FakeRepo)

    count = await _poll_mailbox_in_session(FakeSession(), object(), mailbox_id)

    assert count == 1
    assert order == ["ingest", "commit", "redis"]
