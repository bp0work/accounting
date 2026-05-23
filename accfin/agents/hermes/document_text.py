"""Document text extraction (PDF OCR fallback for images) — Hermes."""

from __future__ import annotations

import base64
import logging

from app.schemas.hermes import DocumentTextRequest, DocumentTextResponse
from agents.hermes.ollama_client import OllamaError, VISION_MODEL, describe_image

logger = logging.getLogger(__name__)

_RECEIPT_OCR_PROMPT = (
    "Transcribe all visible text from this document image. "
    "Include merchant or company name, dates, line items, amounts, currency, "
    "invoice numbers, and totals. Return plain text only — no markdown."
)


async def extract_document_text(request: DocumentTextRequest) -> DocumentTextResponse:
    mime = (request.mime_type or "").lower()
    if mime not in {"image/jpeg", "image/jpg", "image/png"}:
        return DocumentTextResponse(
            success=False,
            error_message=f"Unsupported mime type for vision OCR: {mime}",
        )

    try:
        raw = base64.b64decode(request.content_base64)
        encoded = base64.b64encode(raw).decode("ascii")
        text = await describe_image(
            image_base64=encoded,
            mime_type=mime,
            instruction=_RECEIPT_OCR_PROMPT,
        )
        return DocumentTextResponse(
            success=True,
            extracted_text=text,
            model_used=VISION_MODEL,
        )
    except OllamaError as exc:
        logger.warning("Vision OCR failed: %s", exc)
        return DocumentTextResponse(success=False, error_message=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Document text extraction failed")
        return DocumentTextResponse(success=False, error_message=str(exc))
