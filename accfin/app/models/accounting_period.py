"""ORM: accounting_periods — GL month-end calendar."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_PERIOD_STATUS = ENUM("open", "review", "closed", name="accounting_period_status", create_type=False)


class AccountingPeriod(Base, TimestampMixin):
    __tablename__ = "accounting_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    gl_cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    trial_balance_reviewer: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="finfa.mmlogistix@bp0.work"
    )
    trial_balance_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_balance_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    gl_closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gl_closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(_PERIOD_STATUS, nullable=False, server_default="open")
