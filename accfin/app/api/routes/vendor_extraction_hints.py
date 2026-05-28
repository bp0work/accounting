"""Vendor extraction hints — teach Hermes per-vendor field labels."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.tenant import TENANT_MMLOGISTIX
from app.core.database import get_db_session
from app.core.dependencies import get_current_user, require_client_admin, require_permission
from app.core.exceptions import AppHTTPException
from app.models.user import User
from app.repositories.vendor_extraction_hint import VendorExtractionHintRepository
from app.schemas.auth import TokenData
from app.schemas.vendor_extraction_hint import (
    VendorExtractionHintCreate,
    VendorExtractionHintResponse,
)

router = APIRouter(prefix="/vendor-extraction-hints", tags=["Vendor extraction hints"])


async def _tenant_id(user: TokenData, session: AsyncSession) -> UUID:
    result = await session.execute(select(User.tenant_id).where(User.id == user.user_id))
    tid = result.scalar_one_or_none()
    return tid or TENANT_MMLOGISTIX


@router.post("", response_model=VendorExtractionHintResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_extraction_hint(
    body: VendorExtractionHintCreate,
    user: TokenData = Depends(require_permission("cases:write")),
    session: AsyncSession = Depends(get_db_session),
) -> VendorExtractionHintResponse:
    tid = await _tenant_id(user, session)
    repo = VendorExtractionHintRepository(session)
    row = await repo.upsert(
        tenant_id=tid,
        vendor_name=body.vendor_name,
        field_name=body.field_name,
        field_label=body.field_label,
        field_location=body.field_location,
        example_value=body.example_value,
        date_format=body.date_format,
        created_by=user.user_id,
    )
    await session.commit()
    await session.refresh(row)
    return VendorExtractionHintResponse.model_validate(row)


@router.get("", response_model=list[VendorExtractionHintResponse])
async def list_vendor_extraction_hints(
    vendor_name: str | None = Query(None),
    all_vendors: bool = Query(False, description="List all hints for tenant (Client Admin)"),
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[VendorExtractionHintResponse]:
    if "cases:read" not in user.permissions and "tenant:admin" not in user.permissions:
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN,
            "INSUFFICIENT_PERMISSION",
            "cases:read or tenant:admin is required",
        )
    tid = await _tenant_id(user, session)
    repo = VendorExtractionHintRepository(session)
    if all_vendors:
        if user.role != "client_admin" and "tenant:admin" not in user.permissions:
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN,
                "INSUFFICIENT_PERMISSION",
                "Client Admin access is required to list all vendor hints",
            )
        rows = await repo.list_all(tid)
    elif vendor_name:
        rows = await repo.list_for_vendor(tid, vendor_name, active_only=False)
    else:
        raise AppHTTPException(
            status.HTTP_400_BAD_REQUEST,
            "VENDOR_REQUIRED",
            "vendor_name or all_vendors=true is required",
        )
    return [VendorExtractionHintResponse.model_validate(r) for r in rows]


@router.delete("/{hint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_extraction_hint(
    hint_id: UUID,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    tid = await _tenant_id(user, session)
    repo = VendorExtractionHintRepository(session)
    deleted = await repo.delete(hint_id, tid)
    if not deleted:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Hint not found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
