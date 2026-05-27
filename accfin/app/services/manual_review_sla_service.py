"""Manual-review SLA enforcement — escalate cases > 24 h overdue — `05` §19."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.executive_mail_service import ExecutiveMailService
from app.services.finance_activity_log_service import FinanceActivityLogService

_SLA_HOURS = 24
_FIN_EMAIL = "fin.mmlogistix@bp0.work"


class ManualReviewSlaService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._activity = FinanceActivityLogService(session)
        self._exec_mail = ExecutiveMailService(session)

    async def run(self) -> dict:
        """Escalate every manual_review case that has exceeded the 24-hour SLA."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=_SLA_HOURS)

        result = await self._session.execute(
            select(Case)
            .where(Case.status == "manual_review", Case.created_at < cutoff)
            .order_by(Case.created_at.asc())
        )
        cases = list(result.scalars().all())
        escalated_count = 0

        for case in cases:
            hours_elapsed = int((now - case.created_at).total_seconds() / 3600)
            summary = (
                f"[SLA Breach] Manual review case {case.case_number} has exceeded the "
                f"{_SLA_HOURS}-hour response SLA. In manual_review for {hours_elapsed}h. "
                f"Immediate action required."
            )
            esc = await self._exec_mail.escalate_to_manager(
                case=case,
                email=None,
                reason_code="SLA_BREACH",
                summary=summary,
                error_detail=f"Manual review SLA breach — {hours_elapsed}h elapsed",
                actor_name="sla-monitor",
                actor_type="system",
                target_email_override=_FIN_EMAIL,
                include_escalate=False,
                preserve_case_status=True,
            )
            if esc is not None:
                escalated_count += 1

        await self._activity.log(
            FinanceActivityLogCreate(
                actor_type="system",
                action="sla_breach_escalated",
                summary=(
                    f"SLA monitor: escalated {escalated_count} of {len(cases)} "
                    f"manual_review cases exceeding {_SLA_HOURS}h to {_FIN_EMAIL}"
                ),
                metadata={
                    "escalated_count": escalated_count,
                    "total_overdue": len(cases),
                    "sla_hours": _SLA_HOURS,
                    "target_email": _FIN_EMAIL,
                    "run_at": now.isoformat(),
                },
            )
        )

        await self._session.commit()
        return {"escalated": escalated_count, "sla_hours": _SLA_HOURS}
