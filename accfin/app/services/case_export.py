"""CSV export for finance oversight — transaction case register."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.repositories.case import CaseRepository

CSV_HEADERS = [
    "Case Number",
    "Submitted By",
    "Date Submitted",
    "Type",
    "Document Number",
    "Document Currency",
    "Document Amount",
    "Status",
]


def _format_date_submitted(created_at: datetime | None) -> str:
    if created_at is None:
        return ""
    return created_at.strftime("%d/%m/%Y")


def _format_export_amount(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{Decimal(str(value)):.2f}"


def _document_number(case: Case) -> str:
    meta = case.workflow_metadata or {}
    if not isinstance(meta, dict):
        return ""
    extracted = meta.get("extracted_fields")
    if not isinstance(extracted, dict):
        extracted = {}
    raw = extracted.get("document_number")
    doc = str(raw).strip() if raw is not None else ""
    if case.parent_case_id is not None or case.status in (
        "pending_reversal_approval",
        "reversed",
        "reversal_rejected",
    ):
        source_doc = meta.get("source_document_number")
        if source_doc:
            doc = str(source_doc).strip()
        if doc and not doc.startswith("REV-"):
            doc = f"REV-{doc}"
        elif not doc:
            doc = f"REV-{case.case_number}"
    return doc


def _export_status(case: Case) -> str:
    if case.status in ("reversed", "reversal_rejected"):
        return case.status
    return case.status


async def build_cases_csv(session: AsyncSession, *, date_from: date, date_to: date) -> str:
    repo = CaseRepository(session)
    cases = await repo.list_cases_for_export(date_from=date_from, date_to=date_to)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for case in cases:
        writer.writerow(_case_export_row(case))
    return buffer.getvalue()


def _case_export_row(case: Case) -> list[Any]:
    return [
        case.case_number,
        case.counterparty_name or "",
        _format_date_submitted(case.created_at),
        case.type,
        _document_number(case),
        case.amount_currency or "",
        _format_export_amount(case.amount_value),
        _export_status(case),
    ]
