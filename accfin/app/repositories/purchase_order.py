"""Purchase order lookup — `06` §13a."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase_order import PurchaseOrder


class PurchaseOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_po_number(self, po_number: str) -> PurchaseOrder | None:
        result = await self._session.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )
        return result.scalar_one_or_none()

    def to_po_data(self, po: PurchaseOrder) -> dict:
        return {
            "po_number": po.po_number,
            "counterparty_id": str(po.counterparty_id),
            "status": po.status,
            "currency": po.currency,
            "total_amount": str(po.total_amount),
            "received_amount": str(po.received_amount),
            "line_items": po.line_items,
        }
