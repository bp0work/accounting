"""ORM: tenants — `06` §13.2a."""

import uuid

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
