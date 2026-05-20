"""ORM: coa_accounts, journal_entries, journal_entry_lines — `06` §10–11."""

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
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

_ACCOUNT_TYPE = ENUM(
    "asset", "liability", "equity", "revenue", "expense", name="account_type", create_type=False
)
_JE_STATUS = ENUM(
    "draft", "pending", "posted", "reversed", name="journal_entry_status", create_type=False
)


class CoaAccount(Base, TimestampMixin):
    __tablename__ = "coa_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    account_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(_ACCOUNT_TYPE, nullable=False)
    account_subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coa_accounts.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_bank_account: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    entry_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    case_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(_JE_STATUS, nullable=False, server_default="draft")
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    total_debit: Mapped[Decimal] = mapped_column(Numeric(19, 4), server_default="0")
    total_credit: Mapped[Decimal] = mapped_column(Numeric(19, 4), server_default="0")
    is_balanced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    posted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approvals.id"), nullable=True
    )
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")

    lines: Mapped[list["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan"
    )


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coa_accounts.id"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(19, 4), server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(19, 4), server_default="0")
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    project_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
