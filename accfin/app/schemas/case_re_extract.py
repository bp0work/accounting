"""Re-extract case fields with vendor hints — Finance UI preview (`0.15.00`)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ReExtractResponse(BaseModel):
    case_id: UUID
    case_number: str
    status: str
    extracted_fields: dict[str, str | None]
    extraction_confidence: float | None = None
