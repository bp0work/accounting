"""Phase 3 Mail Gateway acceptance tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.models.mail import MailGatewayConfig
from app.models.user import User
from app.repositories.mail import MailRepository
from app.services.mail.ingest import MailIngestService
from app.services.mail.parser import parse_rfc822
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.integration

SAMPLE = b"""From: vendor@acme.sg
To: accar.mmlogistix@bp0.work
Subject: Test intake
Message-ID: <phase3-test-{suffix}@acme.sg>
Date: Mon, 19 May 2026 10:00:00 +0800
Content-Type: text/plain; charset=utf-8

Body for phase 3 test.
"""


@pytest.mark.asyncio
async def test_pollable_mailboxes_exclude_manager_human(db_session: AsyncSession):
    repo = MailRepository(db_session)
    pollable = await repo.list_pollable_mailboxes()
    assert all(m.mailbox_mode == "executive_agent" for m in pollable)
    addresses = {m.email_address for m in pollable}
    assert "acc.mmlogistix@bp0.work" not in addresses
    assert "cfo.mmlogistix@bp0.work" not in addresses


@pytest.mark.asyncio
async def test_ingest_enqueues_intake_queue(db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_MAIL__ATTACHMENT_STORAGE_PATH", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    addr = f"test-exec-{uuid.uuid4().hex[:8]}@bp0.work"
    mailbox = MailGatewayConfig(
        email_address=addr,
        display_name="Test",
        mailbox_mode="executive_agent",
        server_host="bp0.work",
        server_port=993,
        username=addr,
        password_encrypted="x",
        is_active=True,
        allowed_attachment_types=["application/pdf"],
    )
    db_session.add(mailbox)
    await db_session.flush()

    suffix = uuid.uuid4().hex[:8]
    raw = (
        SAMPLE.replace(b"{suffix}", suffix.encode())
        .replace(b"Body for phase 3 test.", f"Body unique {suffix}.".encode())
    )
    parsed = parse_rfc822(raw, mailbox_address=mailbox.email_address)
    email = await MailIngestService(db_session).ingest(mailbox=mailbox, parsed=parsed)
    await db_session.commit()

    assert email.status == "queued"
    assert email.is_duplicate is False
    redis = get_redis()
    depth = await redis.llen("intake_queue")
    assert depth >= 1


@pytest.mark.asyncio
async def test_duplicate_detection_by_message_id(db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_MAIL__ATTACHMENT_STORAGE_PATH", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    addr = f"dup-test-{uuid.uuid4().hex[:8]}@bp0.work"
    mailbox = MailGatewayConfig(
        email_address=addr,
        mailbox_mode="executive_agent",
        server_host="bp0.work",
        server_port=993,
        username=addr,
        password_encrypted="x",
        is_active=True,
    )
    db_session.add(mailbox)
    await db_session.flush()

    tag = uuid.uuid4().hex[:8]
    raw_first = (
        SAMPLE.replace(b"{suffix}", f"dup1-{tag}".encode())
        .replace(b"Body for phase 3 test.", f"Body dup test {tag}.".encode())
    )
    ingest = MailIngestService(db_session)
    first = await ingest.ingest(
        mailbox=mailbox, parsed=parse_rfc822(raw_first, mailbox_address=mailbox.email_address)
    )
    await db_session.commit()
    # Same Message-ID as first — should dedupe by message_id, not content_hash.
    parsed_dup = parse_rfc822(raw_first, mailbox_address=mailbox.email_address)
    second = await ingest.ingest(mailbox=mailbox, parsed=parsed_dup)
    await db_session.commit()

    assert first.is_duplicate is False
    assert second.is_duplicate is True
    assert second.duplicate_of_id == first.id
    assert second.status == "duplicate"


@pytest.mark.asyncio
async def test_same_content_different_message_id_not_duplicate(
    db_session: AsyncSession, tmp_path, monkeypatch
):
    """Similar body with distinct Message-ID must create separate email rows."""
    monkeypatch.setenv("FINANCE_MAIL__ATTACHMENT_STORAGE_PATH", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    addr = f"content-dup-{uuid.uuid4().hex[:8]}@bp0.work"
    mailbox = MailGatewayConfig(
        email_address=addr,
        mailbox_mode="executive_agent",
        server_host="bp0.work",
        server_port=993,
        username=addr,
        password_encrypted="x",
        is_active=True,
    )
    db_session.add(mailbox)
    await db_session.flush()

    body = b"Shared invoice body text for dedup policy test."
    raw_a = (
        b"From: vendor@example.com\r\n"
        b"To: " + addr.encode() + b"\r\n"
        b"Subject: Invoice A\r\n"
        b"Message-ID: <msg-a-" + uuid.uuid4().hex[:8].encode() + b"@example.com>\r\n"
        b"Date: Mon, 20 May 2026 10:00:00 +0000\r\n"
        b"Content-Type: text/plain\r\n\r\n" + body
    )
    raw_b = (
        b"From: vendor@example.com\r\n"
        b"To: " + addr.encode() + b"\r\n"
        b"Subject: Invoice B\r\n"
        b"Message-ID: <msg-b-" + uuid.uuid4().hex[:8].encode() + b"@example.com>\r\n"
        b"Date: Mon, 20 May 2026 11:00:00 +0000\r\n"
        b"Content-Type: text/plain\r\n\r\n" + body
    )
    ingest = MailIngestService(db_session)
    first = await ingest.ingest(
        mailbox=mailbox, parsed=parse_rfc822(raw_a, mailbox_address=mailbox.email_address)
    )
    second = await ingest.ingest(
        mailbox=mailbox, parsed=parse_rfc822(raw_b, mailbox_address=mailbox.email_address)
    )
    await db_session.commit()

    assert first.is_duplicate is False
    assert second.is_duplicate is False
    assert first.id != second.id


@pytest.mark.asyncio
async def test_mail_status_api(async_client: AsyncClient, auditor_user: User):
    login = await async_client.post(
        "/auth/login",
        json={"username": auditor_user.username, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]
    response = await async_client.get(
        "/mail/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "intake_queue_depth" in data
    assert data["manager_mailboxes_configured"] >= 1
