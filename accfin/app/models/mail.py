"""ORM: emails, email_attachments, mail_gateway_config — `06` §7."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    message_id: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    mailbox_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_addresses: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    cc_addresses: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        ENUM(
            "received",
            "parsed",
            "classified",
            "queued",
            "processed",
            "failed",
            "duplicate",
            "ignored",
            name="email_status",
            create_type=False,
        ),
        nullable=False,
        server_default="received",
    )
    classified_as: Mapped[str | None] = mapped_column(
        ENUM(
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
            name="case_type",
            create_type=False,
        ),
        nullable=True,
    )
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    spf_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dkim_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dmarc_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    case_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    linked_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    processing_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    attachments: Mapped[list["EmailAttachment"]] = relationship(
        "EmailAttachment", back_populates="email", cascade="all, delete-orphan"
    )
    duplicate_of: Mapped["Email | None"] = relationship(
        "Email", remote_side="Email.id", foreign_keys=[duplicate_of_id]
    )


class EmailAttachment(Base):
    __tablename__ = "email_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    wasabi_archive_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    email: Mapped["Email"] = relationship("Email", back_populates="attachments")


class MailGatewayConfig(Base, TimestampMixin):
    __tablename__ = "mail_gateway_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email_address: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mailbox_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="executive_agent"
    )
    escalation_manager_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_outbound_client_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    server_host: Mapped[str] = mapped_column(String(255), nullable=False)
    server_port: Mapped[int] = mapped_column(Integer, nullable=False, server_default="993")
    use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    default_case_type: Mapped[str | None] = mapped_column(
        ENUM(
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
            name="case_type",
            create_type=False,
        ),
        nullable=True,
    )
    routing_rules: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    max_attachment_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="25")
    allowed_attachment_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{application/pdf,image/png,image/jpeg}",
    )
    security_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
