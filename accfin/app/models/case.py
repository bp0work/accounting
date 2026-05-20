"""ORM: counterparty, cases, timeline, notes, attachments — `06` §4."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Counterparty(Base, TimestampMixin):
    __tablename__ = "counterparty"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    first_transaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_transaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")


_CASE_TYPE = ENUM(
    "ar_invoice",
    "ar_payment_advice",
    "ar_credit_note",
    "ap_invoice",
    "ap_po_validation",
    "ap_payment_proposal",
    "treasury_reconciliation",
    "treasury_fx",
    "treasury_suspense",
    "general_inquiry",
    "ar_soa_request",
    name="case_type",
    create_type=False,
)
_CASE_STATUS = ENUM(
    "inbound",
    "classified",
    "processing",
    "pending_approval",
    "approved",
    "posted",
    "completed",
    "rejected",
    "exception",
    "manual_review",
    "on_hold",
    name="case_status",
    create_type=False,
)
_CASE_PRIORITY = ENUM("critical", "high", "medium", "low", name="case_priority", create_type=False)


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(_CASE_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(
        _CASE_STATUS, nullable=False, server_default="inbound"
    )
    priority: Mapped[str] = mapped_column(
        _CASE_PRIORITY, nullable=False, server_default="medium"
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    stp_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=True
    )
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_value: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    amount_currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    converted_amount_value: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    converted_amount_currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(19, 8), server_default="1.0")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    current_approval_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True
    )
    parent_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False, server_default="{}")
    risk_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default="{}"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    workflow_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False, server_default="system")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    timeline: Mapped[list["CaseTimeline"]] = relationship(
        "CaseTimeline", back_populates="case", cascade="all, delete-orphan"
    )
    workflow_instance: Mapped["WorkflowInstance | None"] = relationship(
        "WorkflowInstance", back_populates="case", uselist=False
    )


class CaseTimeline(Base):
    __tablename__ = "case_timeline"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(_CASE_STATUS, nullable=True)
    to_status: Mapped[str | None] = mapped_column(_CASE_STATUS, nullable=True)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    case: Mapped["Case"] = relationship("Case", back_populates="timeline")


class CaseNote(Base, TimestampMixin):
    __tablename__ = "case_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class CaseAttachment(Base):
    __tablename__ = "case_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
