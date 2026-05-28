"""Vendor extraction hint API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VendorExtractionHintCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    field_name: str = Field(..., min_length=1, max_length=100)
    field_label: str = Field(..., min_length=1, max_length=255)
    field_location: str | None = Field(None, max_length=100)
    example_value: str | None = Field(None, max_length=255)
    date_format: str | None = Field(None, max_length=100)


class VendorExtractionHintResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    vendor_name: str
    field_name: str
    field_label: str
    field_location: str | None
    example_value: str | None
    date_format: str | None
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
