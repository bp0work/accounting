"""Case SLA and processing-time helpers for finance oversight UI."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.case import Case

TERMINAL_STATUSES = frozenset({"posted", "completed", "rejected", "case_closed", "case_rejected"})


def processing_time_minutes(case: Case, *, now: datetime | None = None) -> int | None:
    if case.created_at is None:
        return None
    end = case.completed_at or (now or datetime.now(UTC))
    return max(0, int((end - case.created_at).total_seconds() / 60))


def is_case_overdue(case: Case, *, now: datetime | None = None) -> bool:
    if case.status in TERMINAL_STATUSES:
        return False
    now = now or datetime.now(UTC)
    if case.sla_deadline is not None and now > case.sla_deadline:
        return True
    return case.sla_status == "breached"


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)
