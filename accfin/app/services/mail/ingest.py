"""Fetch → normalize → dedupe → persist → enqueue — Phase 3 pipeline."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail import Email, EmailAttachment, MailGatewayConfig
from app.services.attachment_text import extract_attachment_text_sync, sanitize_extracted_text
from app.services.executive_mail_service import ExecutiveMailService
from app.services.mail.dedup import EmailDedupService
from app.services.mail.intake_queue import enqueue_intake
from app.services.mail.parser import ParsedEmail
from app.services.mail.storage import save_attachment
from app.services.mail.text_sanitize import sanitize_text as _sanitize_text


def _sanitize_parsed(parsed: ParsedEmail) -> ParsedEmail:
    """Sanitize all parsed text fields before ORM insert."""
    parsed.from_name = _sanitize_text(parsed.from_name)
    parsed.subject = _sanitize_text(parsed.subject) or "(no subject)"
    parsed.body_text = _sanitize_text(parsed.body_text)
    parsed.body_html = _sanitize_text(parsed.body_html)
    parsed.body_preview = _sanitize_text(parsed.body_preview)
    for att in parsed.attachments:
        att.filename = _sanitize_text(att.filename) or att.filename
    return parsed


class MailIngestService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._dedup = EmailDedupService(session)
        self._executive_mail = ExecutiveMailService(session)

    async def ingest(
        self,
        *,
        mailbox: MailGatewayConfig,
        parsed: ParsedEmail,
    ) -> Email:
        parsed = _sanitize_parsed(parsed)
        dedup = await self._dedup.check(
            message_id=parsed.message_id,
            content_hash=parsed.content_hash,
        )

        metadata = {}
        if parsed.parsed_transaction_number:
            metadata["parsed_transaction_number"] = parsed.parsed_transaction_number

        if dedup.is_duplicate:
            # message_id is UNIQUE — suffix duplicate rows while preserving original header.
            dup_message_id = f"{parsed.message_id}#dup-{uuid4().hex[:8]}"
            email = Email(
                message_id=dup_message_id,
                mailbox_address=mailbox.email_address,
                from_address=parsed.from_address,
                from_name=parsed.from_name,
                to_addresses=parsed.to_addresses,
                cc_addresses=parsed.cc_addresses,
                subject=parsed.subject,
                body_text=parsed.body_text,
                body_html=parsed.body_html,
                body_preview=parsed.body_preview,
                status="duplicate",
                is_duplicate=True,
                duplicate_of_id=dedup.duplicate_of_id,
                content_hash=parsed.content_hash,
                attachment_count=0,
                processing_metadata={**metadata, "dedup_reason": dedup.reason},
                received_at=parsed.received_at,
                processed_at=datetime.now(UTC),
            )
            self._session.add(email)
            await self._session.flush()
            return email

        email = Email(
            message_id=parsed.message_id,
            mailbox_address=mailbox.email_address,
            from_address=parsed.from_address,
            from_name=parsed.from_name,
            to_addresses=parsed.to_addresses,
            cc_addresses=parsed.cc_addresses,
            subject=parsed.subject,
            body_text=parsed.body_text,
            body_html=parsed.body_html,
            body_preview=parsed.body_preview,
            status="parsed",
            is_duplicate=False,
            content_hash=parsed.content_hash,
            attachment_count=0,
            processing_metadata=metadata,
            received_at=parsed.received_at,
        )
        self._session.add(email)
        await self._session.flush()

        max_bytes = mailbox.max_attachment_size_mb * 1024 * 1024
        allowed = set(mailbox.allowed_attachment_types or [])
        count = 0
        for att in parsed.attachments:
            if att.mime_type not in allowed:
                continue
            if len(att.content) > max_bytes:
                continue
            storage_path = save_attachment(
                email_id=email.id, filename=att.filename, content=att.content
            )
            extracted_text = extract_attachment_text_sync(
                content=att.content, mime_type=att.mime_type
            )
            extracted_text = sanitize_extracted_text(extracted_text)
            self._session.add(
                EmailAttachment(
                    email_id=email.id,
                    filename=att.filename,
                    file_size=len(att.content),
                    mime_type=att.mime_type,
                    storage_path=storage_path,
                    content_hash=att.content_hash,
                    extracted_text=extracted_text,
                )
            )
            count += 1

        email.attachment_count = count
        email.status = "queued"
        await self._session.flush()

        await self._executive_mail.log_step(
            action="email_received",
            summary=f"Email received from {parsed.from_address}: {parsed.subject[:120]}",
            actor_type="system",
            actor_name="mail-gateway",
            mailbox_id=mailbox.id,
            email_id=email.id,
            metadata={
                "from_address": parsed.from_address,
                "attachment_count": count,
            },
        )

        await enqueue_intake(email_id=email.id, mailbox=mailbox.email_address)
        email.processed_at = datetime.now(UTC)
        await self._session.flush()
        return email
