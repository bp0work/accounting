"""Accounting calendar exceptions."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.accounting_period import AccountingPeriod


class PeriodClosedError(Exception):
    """Raised when posting to a closed GL period without override."""

    def __init__(self, *, period: AccountingPeriod, posting_date: date) -> None:
        self.period = period
        self.posting_date = posting_date
        super().__init__(
            f"GL period {period.period_year}-{period.period_month:02d} is closed "
            f"(posting date {posting_date})"
        )
