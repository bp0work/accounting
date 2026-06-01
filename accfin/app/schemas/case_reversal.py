"""Expense claim reversal API schemas — `0.15.03-expense-reversal`."""

from uuid import UUID

from pydantic import BaseModel, Field


class RaiseReversalRequest(BaseModel):
    reason: str | None = None


class RaiseReversalResponse(BaseModel):
    reversal_case_id: UUID
    reversal_case_number: str


class ApproveReversalRequest(BaseModel):
    comment: str | None = None
    gl_period_override_reason: str | None = None


class ApproveReversalResponse(BaseModel):
    status: str
    journal_entry_id: UUID


class RejectReversalRequest(BaseModel):
    comment: str = Field(min_length=1)


class RejectReversalResponse(BaseModel):
    status: str
