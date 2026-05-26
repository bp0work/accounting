"""ORM: gl_cutoff_reminders — GL cutoff email notification recipients."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GlCutoffReminder(Base, TimestampMixin):
    __tablename__ = "gl_cutoff_reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notify_7_days: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notify_3_days: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notify_1_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notify_on_date: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
