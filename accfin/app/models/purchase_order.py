"""ORM: purchase_orders — `06` §13a."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_PO_STATUS = ENUM(
    "open",
    "partially_received",
    "fully_received",
    "cancelled",
    "closed",
    name="po_status",
    create_type=False,
)


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    po_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(_PO_STATUS, nullable=False, server_default="open")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="SGD")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    received_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), server_default="0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")
