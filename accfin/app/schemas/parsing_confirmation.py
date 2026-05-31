"""Parsing confirmation API schemas — `0.14.25`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ParsingConfirmationFields(BaseModel):
    document_type: str = "invoice"
    document_number: str | None = None
    document_date: str | None = None
    due_date: str | None = None
    vendor_name: str | None = None
    merchant_name: str | None = None
    total_amount: str | None = None
    gst_amount: str | None = None
    currency: str = "SGD"
    exchange_rate: str | None = None
    payment_terms: str | None = None
    expense_category: str | None = None
    business_purpose: str | None = None
    gl_account_id: UUID | None = None
    sender_validated: bool = False

    @model_validator(mode="after")
    def require_exchange_rate_for_foreign_currency(self) -> ParsingConfirmationFields:
        currency = (self.currency or "SGD").strip().upper()
        if currency != "SGD" and not (self.exchange_rate and str(self.exchange_rate).strip()):
            raise ValueError(
                f"exchange_rate is required when currency is {currency} "
                f"(1 {currency} = ? SGD)"
            )
        return self


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
