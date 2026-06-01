"""Approval API schemas — `05` §7."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MoneyAmount(BaseModel):
    value: str
    currency: str = "SGD"


class UserRef(BaseModel):
    id: UUID
    name: str
    email: str | None = None


class ApprovalListItem(BaseModel):
    id: UUID
    case_id: UUID
    case_number: str
    case_type: str
    tier: int
    status: str
    subject: str | None = None
    description: str | None = None
    amount: MoneyAmount | None = None
    risk_flags: list[str] = Field(default_factory=list)
    sla_deadline: datetime | None = None
    sla_status: str | None = None
    requested_from: UserRef | None = None
    created_at: datetime
    responded_at: datetime | None = None
    response_note: str | None = None
    binding_escalated_to_cfo: bool = False


class ApprovalListResponse(BaseModel):
    data: list[ApprovalListItem]


class ApprovalDetailResponse(ApprovalListItem):
    journal_entry_id: UUID | None = None


class JournalLineAccountUpdate(BaseModel):
    line_number: int = Field(ge=1)
    account_id: UUID


class ApproveRequest(BaseModel):
    note: str | None = None
    journal_entry_id: UUID | None = None
    line_account_updates: list[JournalLineAccountUpdate] = Field(default_factory=list)


class RejectRequest(BaseModel):
    reason: str
    rejection_category: str | None = None
    return_to: str | None = "manual_review"


class EscalateApprovalRequest(BaseModel):
    note: str | None = None


class ApprovalActionResponse(BaseModel):
    id: UUID
    status: str
    decided_at: datetime | None = None
    comments: str | None = None
