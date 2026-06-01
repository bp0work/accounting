"""Trial balance report API schemas."""

from datetime import date

from pydantic import BaseModel, Field


class TrialBalanceRow(BaseModel):
    account_code: str
    account_name: str
    debit: str | None = Field(
        default=None, description="Formatted 2dp; null when zero (display as em dash)"
    )
    credit: str | None = Field(default=None, description="Formatted 2dp; null when zero")
    balance: str = Field(description="debit minus credit; negatives as (12.90)")


class TrialBalanceGroup(BaseModel):
    account_type: str
    label: str
    rows: list[TrialBalanceRow]
    total_balance: str


class TrialBalanceResponse(BaseModel):
    as_at: date
    groups: list[TrialBalanceGroup]
    grand_total_balance: str
