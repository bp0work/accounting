"""Vendor extraction hints — prompt text for Hermes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vendor_extraction_hint import VendorExtractionHint
from app.repositories.vendor_extraction_hint import VendorExtractionHintRepository

DATE_FIELD_NAMES = frozenset({"invoice_date", "due_date", "payment_due_date"})


def format_vendor_hints_prompt(hints: list[VendorExtractionHint], *, vendor_name: str) -> str:
    if not hints:
        return ""
    vendor = vendor_name.strip() or hints[0].vendor_name
    lines: list[str] = [
        f"For vendor {vendor}, note the following field locations on the document:"
    ]
    for hint in hints:
        part = (
            f"- {hint.field_name} is labelled '{hint.field_label}'"
        )
        if hint.field_location:
            part += f" ({hint.field_location})"
        if hint.example_value:
            part += f" (example: '{hint.example_value}')"
        lines.append(part)
        if hint.field_name in DATE_FIELD_NAMES and hint.date_format:
            lines.append(f"  Parse {hint.field_name} using format {hint.date_format}")
    return "\n".join(lines) + "\n\n"


async def load_hints_prompt_block(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    vendor_name: str | None,
) -> str:
    if not vendor_name or not str(vendor_name).strip():
        return ""
    repo = VendorExtractionHintRepository(session)
    hints = await repo.list_for_vendor(tenant_id, vendor_name)
    return format_vendor_hints_prompt(hints, vendor_name=vendor_name)


async def fetch_active_hints(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    vendor_name: str,
) -> list[VendorExtractionHint]:
    repo = VendorExtractionHintRepository(session)
    return await repo.list_for_vendor(tenant_id, vendor_name)
