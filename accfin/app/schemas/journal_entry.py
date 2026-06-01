"""Journal entry schemas for case approval UI."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JournalEntryLineDetail(BaseModel):
    """Single journal line for Finance UI approval panel."""

    line_number: int
    account_id: str
    account_code: str | None = None
    account_name: str | None = None
    debit: str | None = None
    credit: str | None = None
    description: str | None = None


class JournalEntryApprovalDetail(BaseModel):
    """Summary shown on Finance UI journal entry approval panel."""

    vendor: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    document_type: str | None = None
    amount_sgd: str | None = None
    gst: str | None = None
    total: str | None = None
    debit_account: str | None = None
    credit_account: str | None = None
    expense_account_id: str | None = None
    payable_account_id: str | None = None
    lines: list[JournalEntryLineDetail] = Field(default_factory=list)
    approval_tier_label: str | None = None
    journal_entry_id: str | None = None
    entry_number: str | None = None
