"""IMAP poller for executive_agent mailboxes — `17` §2.1.1."""

import asyncio
import imaplib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.crypto import decrypt_field
from app.core.database import get_session_factory
from app.models.mail import Email, MailGatewayConfig
from app.repositories.mail import MailRepository
from app.services.mail.ingest import MailIngestService
from app.services.mail.intake_queue import enqueue_intake
from app.services.mail.parser import parse_rfc822

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MailboxImapSettings:
    """Plain IMAP connection data — safe to use from asyncio.to_thread (no ORM)."""

    email_address: str
    server_host: str
    server_port: int
    use_ssl: bool
    username: str
    password: str


def _imap_settings_from(mailbox: MailGatewayConfig) -> MailboxImapSettings:
    """Read ORM attributes in the async greenlet before any thread handoff."""
    return MailboxImapSettings(
        email_address=mailbox.email_address,
        server_host=mailbox.server_host,
        server_port=mailbox.server_port,
        use_ssl=mailbox.use_ssl,
        username=mailbox.username,
        password=decrypt_field(mailbox.password_encrypted),
    )


def _fetch_unseen(settings: MailboxImapSettings) -> list[bytes]:
    if settings.use_ssl:
        client = imaplib.IMAP4_SSL(settings.server_host, settings.server_port)
    else:
        client = imaplib.IMAP4(settings.server_host, settings.server_port)
    client.login(settings.username, settings.password)
    client.select("INBOX")
    _status, data = client.search(None, "UNSEEN")
    if _status != "OK" or not data or not data[0]:
        client.logout()
        return []
    messages: list[bytes] = []
    for num in data[0].split():
        _fetch_status, fetched = client.fetch(num, "(RFC822)")
        if _fetch_status == "OK" and fetched and fetched[0]:
            messages.append(fetched[0][1])
    client.logout()
    return messages


async def _enqueue_intake_for_email(
    session: AsyncSession,
    email: Email,
    mailbox_address: str,
) -> None:
    """Push parsed email to Redis; log success/failure for manual recovery."""
    if email.status == "duplicate":
        return

    try:
        await enqueue_intake(email_id=email.id, mailbox=mailbox_address)
    except Exception:
        logger.exception(
            "Failed to enqueue email %s (%s) to intake_queue — requeue manually with email_id=%s",
            email.id,
            email.subject,
            email.id,
        )
        meta = dict(email.processing_metadata or {})
        meta["intake_enqueue_failed"] = True
        meta["intake_enqueue_failed_at"] = datetime.now(UTC).isoformat()
        email.processing_metadata = meta
        await session.flush()
        return

    email.status = "queued"
    email.processed_at = datetime.now(UTC)
    await session.flush()
    logger.info(
        "Enqueued email %s (%s) to intake_queue",
        email.id,
        email.subject,
    )


async def _poll_mailbox_in_session(
    session: AsyncSession, mailbox_id: UUID
) -> int:
    repo = MailRepository(session)
    mailbox = await repo.get_mailbox_by_id(mailbox_id)
    if mailbox is None:
        return 0

    imap_settings = _imap_settings_from(mailbox)
    raw_messages = await asyncio.to_thread(_fetch_unseen, imap_settings)

    ingest = MailIngestService(session)
    processed = 0
    for raw in raw_messages:
        parsed = parse_rfc822(raw, mailbox_address=mailbox.email_address)
        email = await ingest.ingest(mailbox=mailbox, parsed=parsed)
        await _enqueue_intake_for_email(session, email, mailbox.email_address)
        processed += 1

    mailbox.last_poll_at = datetime.now(UTC)
    mailbox.last_error = None
    mailbox.error_count = 0
    await session.commit()
    return processed


async def _record_poll_failure(
    session_factory: async_sessionmaker[AsyncSession],
    mailbox_id: UUID,
    exc: Exception,
) -> None:
    async with session_factory() as session:
        repo = MailRepository(session)
        mailbox = await repo.get_mailbox_by_id(mailbox_id)
        if mailbox is None:
            return
        mailbox.last_error = str(exc)[:500]
        mailbox.error_count += 1
        mailbox.last_poll_at = datetime.now(UTC)
        await session.commit()


async def poll_mailbox(mailbox_id: UUID) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await _poll_mailbox_in_session(session, mailbox_id)


async def poll_all_executive_mailboxes() -> dict[str, int]:
    session_factory = get_session_factory()
    mailbox_ids: list[UUID] = []
    email_by_id: dict[UUID, str] = {}

    async with session_factory() as session:
        repo = MailRepository(session)
        for mailbox in await repo.list_pollable_mailboxes():
            mailbox_ids.append(mailbox.id)
            email_by_id[mailbox.id] = mailbox.email_address

    results: dict[str, int] = {}
    for mailbox_id in mailbox_ids:
        address = email_by_id[mailbox_id]
        try:
            count = await poll_mailbox(mailbox_id)
            results[address] = count
            logger.info("Polled %s: %s new messages", address, count)
        except Exception as exc:
            await _record_poll_failure(session_factory, mailbox_id, exc)
            logger.exception("Poll failed for %s", address)
            results[address] = -1
    return results
