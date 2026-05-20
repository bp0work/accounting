"""IMAP poller for executive_agent mailboxes — `17` §2.1.1."""

import asyncio
import imaplib
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_field
from app.core.database import get_session_factory
from app.models.mail import MailGatewayConfig
from app.repositories.mail import MailRepository
from app.services.mail.ingest import MailIngestService
from app.services.mail.parser import parse_rfc822

logger = logging.getLogger(__name__)


def _fetch_unseen(mailbox: MailGatewayConfig) -> list[bytes]:
    password = decrypt_field(mailbox.password_encrypted)
    if mailbox.use_ssl:
        client = imaplib.IMAP4_SSL(mailbox.server_host, mailbox.server_port)
    else:
        client = imaplib.IMAP4(mailbox.server_host, mailbox.server_port)
    client.login(mailbox.username, password)
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


async def poll_mailbox(session: AsyncSession, mailbox: MailGatewayConfig) -> int:
    raw_messages = await asyncio.to_thread(_fetch_unseen, mailbox)
    ingest = MailIngestService(session)
    processed = 0
    for raw in raw_messages:
        parsed = parse_rfc822(raw, mailbox_address=mailbox.email_address)
        await ingest.ingest(mailbox=mailbox, parsed=parsed)
        processed += 1
    mailbox.last_poll_at = datetime.now(UTC)
    mailbox.last_error = None
    mailbox.error_count = 0
    await session.commit()
    return processed


async def poll_all_executive_mailboxes() -> dict[str, int]:
    factory = get_session_factory()
    results: dict[str, int] = {}
    async with factory() as session:
        repo = MailRepository(session)
        mailboxes = await repo.list_pollable_mailboxes()
        for mailbox in mailboxes:
            try:
                count = await poll_mailbox(session, mailbox)
                results[mailbox.email_address] = count
                logger.info("Polled %s: %s new messages", mailbox.email_address, count)
            except Exception as exc:
                await session.rollback()
                mailbox.last_error = str(exc)[:500]
                mailbox.error_count += 1
                mailbox.last_poll_at = datetime.now(UTC)
                await session.commit()
                logger.exception("Poll failed for %s", mailbox.email_address)
                results[mailbox.email_address] = -1
    return results
