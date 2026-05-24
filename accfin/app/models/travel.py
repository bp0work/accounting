"""ORM: employee travel pre-approval requests — `19` travel matching."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


_TRAVEL_STATUS = ENUM(
    "draft",
    "submitted",
    "approved",
    "rejected",
    "cancelled",
    name="travel_request_status",
    create_type=False,
)


class TravelRequest(Base):
    __tablename__ = "travel_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    request_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    employee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    travel_from: Mapped[date] = mapped_column(Date, nullable=False)
    travel_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        _TRAVEL_STATUS, nullable=False, server_default="approved"
    )
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
