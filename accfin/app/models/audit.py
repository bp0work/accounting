"""ORM: audit_logs, system_settings — `06` §13."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_AUDIT_ACTION = ENUM(
    "create",
    "update",
    "delete",
    "approve",
    "reject",
    "post",
    "login",
    "logout",
    "export",
    "override",
    "escalate",
    "delegate",
    "merge",
    "split",
    "match",
    "unmatch",
    "retry",
    "cancel",
    name="audit_action",
    create_type=False,
)
_AUDIT_ENTITY_TYPE = ENUM(
    "case",
    "approval",
    "journal_entry",
    "policy",
    "user",
    "role",
    "workflow",
    "email",
    "queue_message",
    "reconciliation",
    "setting",
    name="audit_entity_type",
    create_type=False,
)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(_AUDIT_ACTION, nullable=False)
    entity_type: Mapped[str] = mapped_column(_AUDIT_ENTITY_TYPE, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    case_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tamper_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    category: Mapped[str] = mapped_column(String(50), nullable=False, server_default="general")
