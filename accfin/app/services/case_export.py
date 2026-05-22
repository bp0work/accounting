"""CSV export for finance oversight — transaction case register."""

from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.case import CaseRepository
from app.services.case_metrics import processing_time_minutes

CSV_HEADERS = [
    "case_number",
    "type",
    "status",
    "counterparty",
    "amount",
    "currency",
    "created_at",
    "completed_at",
    "processing_time_minutes",
    "posted_by",
    "journal_reference",
]


async def build_cases_csv(session: AsyncSession, *, date_from: date, date_to: date) -> str:
    repo = CaseRepository(session)
    rows = await repo.list_cases_for_export(date_from=date_from, date_to=date_to)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for case, journal, posted_by_email in rows:
        writer.writerow(
            [
                case.case_number,
                case.type,
                case.status,
                case.counterparty_name or "",
                str(case.amount_value) if case.amount_value is not None else "",
                case.amount_currency or "",
                case.created_at.isoformat() if case.created_at else "",
                case.completed_at.isoformat() if case.completed_at else "",
                processing_time_minutes(case) if case.created_at else "",
                posted_by_email or "",
                (journal.reference or journal.entry_number) if journal else "",
            ]
        )
    return buffer.getvalue()
