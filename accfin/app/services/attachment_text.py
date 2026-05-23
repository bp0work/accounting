"""Extract plain text from email attachments — PDF locally; images via Hermes/Ollama."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
IMAGE_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png"})


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
    return "\n\n".join(parts)


def extract_attachment_text_sync(*, content: bytes, mime_type: str) -> str | None:
    """Best-effort text extraction without network (PDF only)."""
    mime = (mime_type or "").lower()
    if mime == PDF_MIME:
        try:
            return extract_pdf_text(content) or None
        except Exception:
            logger.exception("PDF text extraction failed")
            return None
    return None


def is_image_mime(mime_type: str) -> bool:
    return (mime_type or "").lower() in IMAGE_MIMES
