"""Case and workflow API schemas — Phase 4."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    type: str
    status: str
    priority: str
    subject: str
    confidence_score: Decimal | None = None
    stp_eligible: bool
    email_id: UUID | None = None
    counterparty_name: str | None = None
    client_vendor_name: str | None = None
    from_address: str | None = None
    amount_value: Decimal | None = None
    amount_currency: str
    risk_flags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    sla_deadline: datetime | None = None
    processing_time_minutes: int | None = None
    is_overdue: bool = False
    processing_stage: str | None = None
    status_group: str | None = None
    status_group_label: str | None = None
    status_label: str | None = None
    error_reason: str | None = None
    status_reason: str | None = None
    last_activity_at: datetime | None = None
    workflow_metadata: dict = Field(default_factory=dict)
    classification_metadata: dict = Field(default_factory=dict)
    linked_gl_period_status: str | None = None
    current_approval_tier: int | None = None
    pending_approval_id: UUID | None = None
    binding_escalated_to_cfo: bool = False


class CaseListResponse(BaseModel):
    data: list[CaseResponse]


class QueueStatusResponse(BaseModel):
    intake_queue: int
    accounts_queue: int
    dead_letter_queue: int
    retry_queue_pending: int


class CaseDashboardResponse(BaseModel):
    queue_depths: QueueStatusResponse
    cases_by_status: dict[str, int]
    average_processing_time_minutes: float | None
    overdue_count: int
    overdue_cases: list[CaseResponse]


class CaseStatusTransitionRequest(BaseModel):
    trigger: str = Field(min_length=1, max_length=50)
    context: dict = Field(default_factory=dict)


class CaseStatusTransitionResponse(BaseModel):
    success: bool
    from_status: str
    to_status: str | None
    trigger: str
    guard_failed: str | None = None


class CaseRetryResponse(BaseModel):
    case_id: UUID
    case_number: str
    message_id: str
    status: str
    previous_status: str


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    actor: str
    description: str | None
    metadata: dict = Field(default_factory=dict, validation_alias="extra_metadata")
    created_at: datetime


class PolicyEvaluateRequest(BaseModel):
    case_id: UUID


class PolicyEvaluateResponse(BaseModel):
    action: dict
    matched_policies: int


