"""Build email + attachment context for Hermes extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hermes import HermesClient
from app.core.config import get_settings
from app.models.mail import Email, EmailAttachment
from app.services.attachment_text import (
    IMAGE_MIMES,
    extract_attachment_text_sync,
    is_image_mime,
    sanitize_extracted_text,
)

logger = logging.getLogger(__name__)


def _read_attachment_bytes(storage_path: str) -> bytes | None:
    base = Path(get_settings().attachment_storage_path)
    path = base / storage_path
    if not path.is_file():
        logger.warning("Attachment file missing: %s", path)
        return None
    return path.read_bytes()


async def ensure_attachment_texts(
    session: AsyncSession,
    email_id: UUID,
    *,
    hermes: HermesClient | None = None,
) -> None:
    """Populate `EmailAttachment.extracted_text` for PDFs and images when missing."""
    result = await session.execute(
        select(EmailAttachment).where(EmailAttachment.email_id == email_id)
    )
    attachments = list(result.scalars().all())
    if not attachments:
        return

    client = hermes or HermesClient(timeout=120.0)
    changed = False
    for att in attachments:
        if att.extracted_text and att.extracted_text.strip():
            continue
        content = _read_attachment_bytes(att.storage_path)
        if content is None:
            continue

        text = extract_attachment_text_sync(content=content, mime_type=att.mime_type)
        if not text and is_image_mime(att.mime_type):
            try:
                text = await client.extract_document_text(
                    filename=att.filename,
                    mime_type=att.mime_type,
                    content_base64=content,
                )
            except Exception:
                logger.exception("Image OCR via Hermes failed for %s", att.filename)

        if text and text.strip():
            att.extracted_text = sanitize_extracted_text(text.strip())
            changed = True

    if changed:
        await session.flush()


async def build_extraction_context(
    session: AsyncSession,
    email_id: UUID | None,
    *,
    hermes: HermesClient | None = None,
) -> tuple[str, UUID | None, str]:
    """
    Returns (combined_document_text, primary_attachment_id, email_body).
    Combined text includes subject, body, and all attachment texts for Ollama.
    """
    if not email_id:
        return "", None, ""

    await ensure_attachment_texts(session, email_id, hermes=hermes)

    email = await session.get(Email, email_id)
    if email is None:
        return "", None, ""

    body = (email.body_text or email.body_preview or "").strip()
    parts: list[str] = []
    if body:
        parts.append(body)

    result = await session.execute(
        select(EmailAttachment)
        .where(EmailAttachment.email_id == email_id)
        .order_by(EmailAttachment.created_at)
    )
    primary_id: UUID | None = None
    for att in result.scalars().all():
        if primary_id is None:
            primary_id = att.id
        if att.extracted_text and att.extracted_text.strip():
            parts.append(f"Attachment ({att.filename}):\n{att.extracted_text.strip()}")
        elif att.mime_type in IMAGE_MIMES or att.mime_type == "application/pdf":
            parts.append(f"Attachment ({att.filename}): [no text extracted]")

    return "\n\n".join(parts), primary_id, body
