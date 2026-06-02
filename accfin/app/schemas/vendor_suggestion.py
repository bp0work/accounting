"""Vendor name autocomplete suggestions for parsing confirmation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VendorSuggestionResponse(BaseModel):
    name: str
    source: Literal["counterparty", "case_history"]
    counterparty_type: str | None = None
    email: str | None = None


class VendorSuggestionQuery(BaseModel):
    search: str = Field(..., min_length=2)
    limit: int = Field(default=10, ge=1, le=20)
