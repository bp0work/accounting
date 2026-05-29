"""Journal entry schemas for case approval UI."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JournalEntryApprovalDetail(BaseModel):
    """Summary shown on Finance UI journal entry approval panel."""

    vendor: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    document_type: str | None = None
    amount_sgd: str | None = None
    gst: str | None = None
    total: str | None = None
    debit_account: str | None = None
    credit_account: str | None = None
    approval_tier_label: str | None = None
    journal_entry_id: str | None = None
    entry_number: str | None = None
