"""ORM: rental and director expense agreements."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, Date, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RentalAgreement(Base, TimestampMixin):
    __tablename__ = "rental_agreements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    property_address: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_rent_sgd: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    business_use_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="100")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    landlord_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landlord_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class DirectorExpenseAgreement(Base, TimestampMixin):
    __tablename__ = "director_expense_agreements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    director_name: Mapped[str] = mapped_column(String(255), nullable=False)
    director_email: Mapped[str] = mapped_column(String(255), nullable=False)
    authorised_expense_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    monthly_limit_sgd: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
