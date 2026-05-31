"""ORM: expense claims, line items, policies — `19` §12."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CHAR,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

_EXPENSE_CLAIM_STATUS = ENUM(
    "draft",
    "submitted",
    "processing",
    "pending_approval",
    "approved",
    "rejected",
    "posted",
    "completed",
    "exception",
    "manual_review",
    name="expense_claim_status",
    create_type=False,
)
_EXPENSE_CATEGORY = ENUM(
    "accommodation",
    "airfare",
    "ground_transport",
    "meals",
    "entertainment",
    "office_supplies",
    "training",
    "telecommunications",
    "professional_fees",
    "other",
    name="expense_category",
    create_type=False,
)


class ExpenseClaim(Base, TimestampMixin):
    __tablename__ = "expense_claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False
    )
    case_number: Mapped[str] = mapped_column(String(20), nullable=False)
    claimant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    claimant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    submission_date: Mapped[date] = mapped_column(Date, nullable=False)
    claim_period_from: Mapped[date] = mapped_column(Date, nullable=False)
    claim_period_to: Mapped[date] = mapped_column(Date, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="SGD")
    total_claimed: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    total_approved: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    status: Mapped[str] = mapped_column(_EXPENSE_CLAIM_STATUS, nullable=False)
    policy_violations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    risk_flags: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    approval_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    workflow_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    stp_eligible: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    submitted_via: Mapped[str] = mapped_column(String(20), nullable=False, server_default="email")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    line_items: Mapped[list["ExpenseLineItem"]] = relationship(
        "ExpenseLineItem",
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="ExpenseLineItem.line_number",
    )


class ExpenseLineItem(Base, TimestampMixin):
    __tablename__ = "expense_line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    expense_claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(_EXPENSE_CATEGORY, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="SGD")
    amount_claimed: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    amount_approved: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    amount_sgd: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    receipt_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_attachments.id"), nullable=True
    )
    policy_compliant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    policy_violation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    gl_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coa_accounts.id"), nullable=True
    )
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    project_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    claim: Mapped["ExpenseClaim"] = relationship("ExpenseClaim", back_populates="line_items")


class ExpensePolicy(Base, TimestampMixin):
    __tablename__ = "expense_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(_EXPENSE_CATEGORY, nullable=True)
    applies_to_all_categories: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    applies_to_all_departments: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    daily_limit: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    per_claim_limit: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    requires_receipt_above: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, server_default="50.00"
    )
    requires_approval_above: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, server_default="500.00"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1.0.0")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
