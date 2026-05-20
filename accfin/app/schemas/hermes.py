"""Hermes API schemas — `04` §6.1."""

from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentInput(BaseModel):
    attachment_id: UUID
    filename: str
    mime_type: str
    extracted_text: str | None = None
    page_count: int | None = None


class CounterpartyHint(BaseModel):
    name: str
    code: str | None = None
    type: str | None = None
    is_recurring: bool = False


class ClassifyEmailRequest(BaseModel):
    case_id: UUID | None = None
    email_id: UUID
    subject: str
    body_preview: str = ""
    from_address: str
    mailbox: str | None = None
    attachments: list[AttachmentInput] = Field(default_factory=list)
    known_counterparties: list[CounterpartyHint] = Field(default_factory=list)
    valid_case_types: list[str] = Field(default_factory=list)


class ClassifyEmailOutput(BaseModel):
    case_type: str
    stp_eligible: bool = False
    counterparty_match: str | None = None
    reasoning: str = ""


class ClassifyEmailResponse(BaseModel):
    success: bool = True
    confidence_score: float = 0.0
    model_used: str = "hermes-stub"
    prompt_version: str = "email_classify-v1"
    processing_time_ms: int = 0
    output: ClassifyEmailOutput | None = None
    error_code: str | None = None
    error_message: str | None = None
