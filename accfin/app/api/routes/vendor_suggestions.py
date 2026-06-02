"""Vendor name autocomplete for parsing confirmation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.schemas.auth import TokenData
from app.schemas.vendor_suggestion import VendorSuggestionResponse
from app.services.vendor_suggestions import get_vendor_suggestions

router = APIRouter(prefix="/vendor-suggestions", tags=["Vendor suggestions"])


@router.get("", response_model=list[VendorSuggestionResponse])
async def list_vendor_suggestions(
    search: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=20),
    _user: TokenData = Depends(require_permission("cases:read")),
    session: AsyncSession = Depends(get_db_session),
) -> list[VendorSuggestionResponse]:
    return await get_vendor_suggestions(session, search, limit=limit)
