"""ORM: reconciliation tables — `06` §12."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CHAR,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_RECON_STATUS = ENUM(
    "in_progress", "completed", "failed", name="reconciliation_status", create_type=False
)


class ReconciliationRun(Base, TimestampMixin):
    __tablename__ = "reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coa_accounts.id"), nullable=False
    )
    statement_period_from: Mapped[date] = mapped_column(Date, nullable=False)
    statement_period_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        _RECON_STATUS, nullable=False, server_default="in_progress"
    )
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(19, 4), server_default="0")
    closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    statement_balance: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    total_bank_transactions: Mapped[int] = mapped_column(Integer, server_default="0")
    total_ledger_transactions: Mapped[int] = mapped_column(Integer, server_default="0")
    matched_count: Mapped[int] = mapped_column(Integer, server_default="0")
    unmatched_count: Mapped[int] = mapped_column(Integer, server_default="0")
    auto_matched_count: Mapped[int] = mapped_column(Integer, server_default="0")
    manual_matched_count: Mapped[int] = mapped_column(Integer, server_default="0")
    match_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    started_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_rules_used: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )


class ReconciliationBankItem(Base):
    __tablename__ = "reconciliation_bank_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    is_matched: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    match_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ReconciliationLedgerItem(Base):
    __tablename__ = "reconciliation_ledger_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    journal_entry_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entry_lines.id"), nullable=True
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    is_matched: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    match_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False
    )
    bank_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_bank_items.id"), nullable=False
    )
    ledger_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_ledger_items.id"), nullable=False
    )
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    match_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matched_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    is_voided: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
