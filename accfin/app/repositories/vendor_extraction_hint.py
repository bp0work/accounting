"""Vendor extraction hints persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vendor_extraction_hint import VendorExtractionHint


class VendorExtractionHintRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_vendor(
        self, tenant_id: UUID, vendor_name: str, *, active_only: bool = True
    ) -> list[VendorExtractionHint]:
        normalized = vendor_name.strip()
        stmt = select(VendorExtractionHint).where(
            VendorExtractionHint.tenant_id == tenant_id,
            func.lower(VendorExtractionHint.vendor_name) == normalized.lower(),
        )
        if active_only:
            stmt = stmt.where(VendorExtractionHint.is_active.is_(True))
        stmt = stmt.order_by(VendorExtractionHint.field_name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, tenant_id: UUID, *, active_only: bool = False) -> list[VendorExtractionHint]:
        stmt = (
            select(VendorExtractionHint)
            .where(VendorExtractionHint.tenant_id == tenant_id)
            .order_by(VendorExtractionHint.vendor_name, VendorExtractionHint.field_name)
        )
        if active_only:
            stmt = stmt.where(VendorExtractionHint.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, hint_id: UUID, tenant_id: UUID) -> VendorExtractionHint | None:
        result = await self._session.execute(
            select(VendorExtractionHint).where(
                VendorExtractionHint.id == hint_id,
                VendorExtractionHint.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        vendor_name: str,
        field_name: str,
        field_label: str,
        field_location: str | None,
        example_value: str | None,
        date_format: str | None,
        created_by: UUID | None,
    ) -> VendorExtractionHint:
        vendor = vendor_name.strip()
        field = field_name.strip()
        stmt = (
            insert(VendorExtractionHint)
            .values(
                tenant_id=tenant_id,
                vendor_name=vendor,
                field_name=field,
                field_label=field_label.strip(),
                field_location=(field_location or "").strip() or None,
                example_value=(example_value or "").strip() or None,
                date_format=(date_format or "").strip() or None,
                is_active=True,
                created_by=created_by,
            )
            .on_conflict_do_update(
                index_elements=[
                    VendorExtractionHint.tenant_id,
                    func.lower(VendorExtractionHint.vendor_name),
                    VendorExtractionHint.field_name,
                ],
                set_={
                    "field_label": field_label.strip(),
                    "field_location": (field_location or "").strip() or None,
                    "example_value": (example_value or "").strip() or None,
                    "date_format": (date_format or "").strip() or None,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
            .returning(VendorExtractionHint)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        await self._session.flush()
        return row

    async def delete(self, hint_id: UUID, tenant_id: UUID) -> bool:
        row = await self.get(hint_id, tenant_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
