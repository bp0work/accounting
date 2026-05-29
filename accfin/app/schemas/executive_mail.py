"""Schemas for executive email SOP — `05` §8.8a, §19.1."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FinanceDailyLogJobRequest(BaseModel):
    business_date: date | None = None
    force: bool = False


class FinanceDailyLogJobResponse(BaseModel):
    status: str
    business_date: date
    recipient: str | None = None
    row_count: int | None = None
    smtp_message_id: str | None = None
    sent_at: datetime | None = None
    wasabi_log_path: str | None = None
    attachment_filename: str | None = None
    reason: str | None = None
    last_sent_at: datetime | None = None
    message: str | None = None


class CaseEscalationRespondRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject|request_info)$")
    comment: str | None = Field(default=None, max_length=4000)


class EscalationRespondResult(BaseModel):
    escalation_id: UUID
    case_id: UUID
    action: str
    status: str
    child_escalation_id: UUID | None = None
    target_email: str | None = None
    responded_at: datetime
    message: str | None = None
    manager_comment: str | None = None


class EscalationRespondContext(BaseModel):
    escalation_id: UUID
    case_id: UUID
    case_number: str
    action: str
    status: str
    already_responded: bool = False
    result: EscalationRespondResult | None = None


class FinanceActivityLogCreate(BaseModel):
    actor_type: str = Field(pattern="^(worker|manager|human|system)$")
    action: str
    summary: str
    actor_name: str | None = None
    mailbox_id: UUID | None = None
    case_id: UUID | None = None
    email_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)
