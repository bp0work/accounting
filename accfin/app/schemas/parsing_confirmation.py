"""Parsing confirmation API schemas — `0.14.25`."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ParsingConfirmationFields(BaseModel):
    document_type: str = "invoice"
    document_number: str | None = None
    document_date: str | None = None
    due_date: str | None = None
    vendor_name: str | None = None
    total_amount: str | None = None
    gst_amount: str | None = None
    currency: str = "SGD"
    payment_terms: str | None = None
    sender_validated: bool = False


class ConfirmParsingRequest(BaseModel):
    extracted_fields: ParsingConfirmationFields


class ConfirmParsingResponse(BaseModel):
    case_id: UUID
    case_number: str
    status: str
    message_id: str
    parsing_confirmed_by: UUID
    parsing_confirmed_at: datetime
    correction_count: int


class RejectParsingRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class RejectParsingResponse(BaseModel):
    case_id: UUID
    case_number: str
    status: str
