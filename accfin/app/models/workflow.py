"""ORM: workflow definitions, instances, transitions — `06` §4.6–4.8."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

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
    name="case_type",
    create_type=False,
)


class WorkflowDefinition(Base, TimestampMixin):
    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    case_type: Mapped[str] = mapped_column(_CASE_TYPE, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id"), nullable=False
    )
    current_state: Mapped[str] = mapped_column(_CASE_STATUS, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    case: Mapped["Case"] = relationship("Case", back_populates="workflow_instance")
    transitions: Mapped[list["WorkflowTransition"]] = relationship(
        "WorkflowTransition", back_populates="instance", cascade="all, delete-orphan"
    )


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(_CASE_STATUS, nullable=False)
    to_state: Mapped[str] = mapped_column(_CASE_STATUS, nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    instance: Mapped["WorkflowInstance"] = relationship(
        "WorkflowInstance", back_populates="transitions"
    )
