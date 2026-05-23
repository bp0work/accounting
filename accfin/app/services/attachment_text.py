"""Extract plain text from email attachments — PDF locally; images via Hermes/Ollama."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
IMAGE_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png"})


def sanitize_extracted_text(text: str | None) -> str | None:
    """Remove NUL bytes — PostgreSQL text columns reject \\x00."""
    from app.services.mail.text_sanitize import sanitize_text

    return sanitize_text(text)


def extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF text extraction") from exc

    reader = PdfReader(io.BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())
    return sanitize_extracted_text("\n\n".join(parts)) or ""


def extract_attachment_text_sync(*, content: bytes, mime_type: str) -> str | None:
    """Best-effort text extraction without network (PDF only)."""
    mime = (mime_type or "").lower()
    if mime == PDF_MIME:
        try:
            text = extract_pdf_text(content) or None
            return sanitize_extracted_text(text)
        except Exception:
            logger.exception("PDF text extraction failed")
            return None
    return None


def is_image_mime(mime_type: str) -> bool:
    return (mime_type or "").lower() in IMAGE_MIMES
