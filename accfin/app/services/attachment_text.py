"""Extract plain text from email attachments — PDF/DOCX locally; images via Hermes/Ollama."""

from __future__ import annotations

import io
import logging
import re

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
IMAGE_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png"})


def sanitize_extracted_text(text: str | None) -> str | None:
    """Remove NUL bytes — PostgreSQL text columns reject \\x00."""
    from app.services.mail.text_sanitize import sanitize_text

    return sanitize_text(text)


_WORD_FRAGMENT_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDec\s+em\s+ber\b", re.I), "December"),
    (re.compile(r"\bJan\s+u\s+ary\b", re.I), "January"),
    (re.compile(r"\bFeb\s+ru\s+ary\b", re.I), "February"),
    (re.compile(r"\bSep\s+tem\s+ber\b", re.I), "September"),
    (re.compile(r"\bNov\s+em\s+ber\b", re.I), "November"),
]


def normalize_fragmented_text(text: str) -> str:
    """
    Repair common DOCX run-splitting artefacts.

    Examples: HO-202 512 -01 → HO-202512-01; Dec em ber → December
    """
    if not text:
        return text

    # Join digit groups split by spaces (invoice numbers, amounts).
    cleaned = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    cleaned = re.sub(r"(?<=-)\s+", "", cleaned)
    cleaned = re.sub(r"\s+(?=-)", "", cleaned)

    # Merge single-character token runs (split words from XML runs).
    tokens = cleaned.split()
    merged: list[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if len(token) == 1 and token.isalpha():
            buf = token
            j = idx + 1
            while j < len(tokens) and len(tokens[j]) == 1 and tokens[j].isalpha():
                buf += tokens[j]
                j += 1
            if len(buf) > 1:
                merged.append(buf)
                idx = j
                continue
        merged.append(token)
        idx += 1

    result = " ".join(merged)
    for pattern, replacement in _WORD_FRAGMENT_REPAIRS:
        result = pattern.sub(replacement, result)
    return result


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
    raw = "\n\n".join(parts)
    return sanitize_extracted_text(normalize_fragmented_text(raw)) or ""


def extract_docx_text(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required for DOCX text extraction") from exc

    document = Document(io.BytesIO(content))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    raw = "\n\n".join(paragraphs)
    return sanitize_extracted_text(normalize_fragmented_text(raw)) or ""


def extract_attachment_text_sync(*, content: bytes, mime_type: str) -> str | None:
    """Best-effort text extraction without network (PDF and DOCX)."""
    mime = (mime_type or "").lower()
    if mime == PDF_MIME:
        try:
            text = extract_pdf_text(content) or None
            return sanitize_extracted_text(text)
        except Exception:
            logger.exception("PDF text extraction failed")
            return None
    if mime == DOCX_MIME:
        try:
            text = extract_docx_text(content) or None
            return sanitize_extracted_text(text)
        except Exception:
            logger.exception("DOCX text extraction failed")
            return None
    return None


def is_image_mime(mime_type: str) -> bool:
    return (mime_type or "").lower() in IMAGE_MIMES
