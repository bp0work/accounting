"""ORM: finance_activity_log, case_escalations, pending_outbound_emails — `06` §7.4–§7.6."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_ESCALATION_STATUS = ENUM(
    "pending",
    "approved",
    "rejected",
    "escalated",
    "expired",
    "cancelled",
    name="case_escalation_status",
    create_type=False,
)
_OUTBOUND_STATUS = ENUM(
    "awaiting_manager_approval",
    "approved",
    "sent",
    "rejected",
    "cancelled",
    name="pending_outbound_email_status",
    create_type=False,
)


class FinanceActivityLog(Base):
    __tablename__ = "finance_activity_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    mailbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_gateway_config.id"), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CaseEscalation(Base, TimestampMixin):
    __tablename__ = "case_escalations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False
    )
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True
    )
    originating_mailbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_gateway_config.id"), nullable=False
    )
    target_mailbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_gateway_config.id"), nullable=True
    )
    target_email: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_escalation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_escalations.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(_ESCALATION_STATUS, nullable=False, server_default="pending")
    reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PendingOutboundEmail(Base, TimestampMixin):
    __tablename__ = "pending_outbound_emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True
    )
    mailbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_gateway_config.id"), nullable=False
    )
    approver_mailbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_gateway_config.id"), nullable=True
    )
    to_addresses: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    cc_addresses: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_plain: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="clarification")
    status: Mapped[str] = mapped_column(
        _OUTBOUND_STATUS, nullable=False, server_default="awaiting_manager_approval"
    )
    rejection_reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manager_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    smtp_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
