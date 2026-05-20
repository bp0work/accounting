"""Expense claim API schemas — `05` §18."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


API_CATEGORY_MAP = {
    "transport": "ground_transport",
    "meals": "meals",
    "accommodation": "accommodation",
    "office": "office_supplies",
    "entertainment": "entertainment",
}


class ExpenseClaimSubmitRequest(BaseModel):
    category: str
    merchant: str = Field(max_length=200)
    amount_value: str
    amount_currency: str = "SGD"
    receipt_date: date
    purpose: str = Field(min_length=10, max_length=500)
    attachment_ids: list[UUID] = Field(min_length=1)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in API_CATEGORY_MAP:
            raise ValueError(
                "category must be one of: transport, meals, accommodation, office, entertainment"
            )
        return v


class ExpenseClaimSubmitResponse(BaseModel):
    expense_claim_id: UUID
    case_id: UUID
    case_number: str
    status: str
    created_at: datetime


class ExpenseClaimSubmitEnvelope(BaseModel):
    data: ExpenseClaimSubmitResponse


class ExpenseLineItemResponse(BaseModel):
    id: UUID
    line_number: int
    expense_date: date
    category: str
    description: str
    merchant: str | None = None
    amount_claimed: str
    amount_currency: str = "SGD"
    policy_compliant: bool | None = None


class ExpenseClaimListItem(BaseModel):
    expense_claim_id: UUID
    case_number: str
    merchant: str | None = None
    category: str | None = None
    amount_value: str
    amount_currency: str
    receipt_date: date | None = None
    status: str
    risk_flags: list[str] = Field(default_factory=list)
    created_at: datetime


class ExpenseClaimListResponse(BaseModel):
    data: list[ExpenseClaimListItem]


class ExpenseClaimDetail(BaseModel):
    id: UUID
    case_id: UUID
    case_number: str
    claimant_user_id: UUID
    category: str | None = None
    merchant: str | None = None
    amount_value: str
    amount_currency: str
    receipt_date: date | None = None
    purpose: str | None = None
    status: str
    risk_flags: list[str] = Field(default_factory=list)
    policy_violations: list = Field(default_factory=list)
    partial_extraction: bool = False
    line_items: list[ExpenseLineItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ExpenseClaimDetailEnvelope(BaseModel):
    data: ExpenseClaimDetail


class ExpenseClaimStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v != "withdrawn":
            raise ValueError("Only withdrawn status is supported via this endpoint")
        return v
