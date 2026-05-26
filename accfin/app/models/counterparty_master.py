"""Counterparty subaccounts, payment terms, tenant tax codes — `06` §4.1a–c."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PaymentTerm(Base, TimestampMixin):
    __tablename__ = "payment_terms"
    __table_args__ = (CheckConstraint("due_days >= 0", name="payment_terms_due_days_nonneg"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    due_days: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    discount_if_paid_within_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_invoice_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class CounterpartyAccount(Base, TimestampMixin):
    __tablename__ = "counterparty_accounts"
    __table_args__ = (
        CheckConstraint(
            "role IN ('bill_to', 'ship_to', 'remit_to', 'statement_to', 'other')",
            name="counterparty_accounts_role_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    counterparty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id", ondelete="CASCADE"), nullable=False
    )
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, server_default="bill_to")
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_terms.id"), nullable=True
    )
    credit_limit_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    credit_limit_currency: Mapped[str | None] = mapped_column(CHAR(3), server_default="SGD", nullable=True)
    counterparty_gst_reg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    payment_term: Mapped[PaymentTerm | None] = relationship("PaymentTerm")


class TenantTaxCode(Base, TimestampMixin):
    __tablename__ = "tenant_tax_codes"
    __table_args__ = (
        CheckConstraint("rate >= 0 AND rate <= 1", name="tenant_tax_codes_rate_range"),
        CheckConstraint(
            "direction IN ('output', 'input', 'both')",
            name="tenant_tax_codes_direction_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    output_gl_account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_gl_account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
