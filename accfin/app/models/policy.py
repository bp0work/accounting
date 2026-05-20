"""ORM: policies, approvals — `06` §4.9–4.10."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_APPROVAL_STATUS = ENUM(
    "pending",
    "approved",
    "rejected",
    "escalated",
    "expired",
    name="approval_status",
    create_type=False,
)


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        _APPROVAL_STATUS, nullable=False, server_default="pending"
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    amount_value: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    amount_currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
