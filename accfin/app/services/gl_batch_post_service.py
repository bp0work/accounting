"""GL batch posting — find approved journal entries and post to GL — `05` §19."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.ledger import JournalEntry
from app.models.policy import Approval
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.finance_activity_log_service import FinanceActivityLogService


class GlBatchPostService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._activity = FinanceActivityLogService(session)

    async def run(self) -> dict:
        """Post all approved draft journals; close associated cases."""
        now = datetime.now(UTC)
        today = now.date()
        posted_count = 0
        failed_count = 0
        total_amount = Decimal("0")

        # Draft journals linked to an approved Approval record
        result = await self._session.execute(
            select(JournalEntry)
            .join(Approval, JournalEntry.approval_id == Approval.id)
            .where(
                JournalEntry.status == "draft",
                Approval.status == "approved",
            )
        )
        entries = list(result.scalars().all())

        for entry in entries:
            try:
                entry.status = "posted"
                entry.posting_date = today
                entry.posted_at = now
                total_amount += entry.total_debit or Decimal("0")
                posted_count += 1

                if entry.case_id:
                    cr = await self._session.execute(
                        select(Case).where(Case.id == entry.case_id)
                    )
                    case = cr.scalar_one_or_none()
                    if case and case.status not in (
                        "case_closed", "case_rejected", "completed", "rejected"
                    ):
                        case.status = "case_closed"
                        case.completed_at = now

            except Exception:
                failed_count += 1

        # Cases already journal_posted but not yet closed (e.g. binding-auth posted them)
        jp_result = await self._session.execute(
            select(Case).where(Case.status == "journal_posted")
        )
        for case in jp_result.scalars().all():
            case.status = "case_closed"
            case.completed_at = case.completed_at or now

        await self._session.flush()

        await self._activity.log(
            FinanceActivityLogCreate(
                actor_type="system",
                action="gl_batch_posted",
                summary=(
                    f"GL batch: posted {posted_count} journal entries, "
                    f"{failed_count} failed, total SGD {total_amount:,.2f}"
                ),
                metadata={
                    "posted_count": posted_count,
                    "failed_count": failed_count,
                    "total_amount": str(total_amount),
                    "run_at": now.isoformat(),
                },
            )
        )

        await self._session.commit()
        return {
            "posted": posted_count,
            "failed": failed_count,
            "total_amount": str(total_amount),
        }
