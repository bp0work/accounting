"""Reconciliation API schemas — `05` §13."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BankItemInput(BaseModel):
    transaction_date: date
    description: str | None = None
    reference: str | None = None
    amount: str
    currency: str = "SGD"


class StartReconciliationRequest(BaseModel):
    account_id: UUID
    statement_period_from: date
    statement_period_to: date
    statement_balance: str | None = None
    opening_balance: str = "0"
    bank_items: list[BankItemInput] = Field(default_factory=list)


class StartReconciliationResponse(BaseModel):
    reconciliation_id: UUID
    status: str
    estimated_completion: str | None = None


class ReconciliationRunResponse(BaseModel):
    id: UUID
    account_id: UUID
    statement_period_from: date
    statement_period_to: date
    status: str
    opening_balance: Decimal
    closing_balance: Decimal | None = None
    statement_balance: Decimal | None = None
    total_bank_transactions: int
    total_ledger_transactions: int
    matched_count: int
    unmatched_count: int
    auto_matched_count: int
    manual_matched_count: int
    match_rate: Decimal | None = None
    match_rules_used: list[str] = Field(default_factory=list)
    error_message: str | None = None

    model_config = {"from_attributes": True}


class UnmatchedItemResponse(BaseModel):
    id: UUID
    side: str
    transaction_date: date
    description: str | None = None
    reference: str | None = None
    amount: str
    currency: str


class UnmatchedItemsResponse(BaseModel):
    reconciliation_id: UUID
    unmatched_count: int
    items: list[UnmatchedItemResponse] = Field(default_factory=list)
