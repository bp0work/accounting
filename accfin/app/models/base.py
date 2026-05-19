"""Shared SQLAlchemy base and mixins — `16` §5.1, `06` §1."""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

pk_uuid = Annotated[
    uuid.UUID,
    mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        sort_order=-10,
    ),
]

ts_now = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False),
]


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
        sort_order=98,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
        sort_order=99,
    )
