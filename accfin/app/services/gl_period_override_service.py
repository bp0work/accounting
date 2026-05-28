"""Authorize retroactive posting to closed GL periods."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.models.accounting_period import AccountingPeriod
from app.models.case import Case
from app.models.user import User
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.accounting_calendar import assert_period_allows_posting
from app.services.finance_activity_log_service import FinanceActivityLogService
from app.services.queue_router import enqueue_accounts
from fastapi import status


class GlPeriodOverrideService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._activity = FinanceActivityLogService(session)

    async def override_and_requeue(
        self,
        *,
        period_id: UUID,
        case_id: UUID,
        override_reason: str,
        user: TokenData,
    ) -> dict:
        reason = (override_reason or "").strip()
        if not reason:
            raise AppHTTPException(
                status.HTTP_400_BAD_REQUEST, "INVALID_REASON", "override_reason is required"
            )

        period = await self._session.get(AccountingPeriod, period_id)
        if period is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Period not found")
        if period.status != "closed":
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "PERIOD_NOT_CLOSED",
                "Override is only required for closed periods",
            )

        case = await self._cases.get(case_id)
        if case is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Case not found")

        db_user = await self._session.get(User, user.user_id)
        poster = db_user.email if db_user else str(user.user_id)

        await assert_period_allows_posting(
            self._session,
            date_from_period(period),
            override=True,
            override_reason=reason,
            posted_by=poster,
            case_id=case.id,
            case_number=case.case_number,
        )

        meta = dict(case.workflow_metadata or {})
        meta.update(
            {
                "gl_period_override": True,
                "gl_period_override_reason": reason,
                "gl_period_posted_by": poster,
                "gl_period_id": str(period.id),
                "error_type": None,
                "reason_code": None,
            }
        )
        meta.pop("error_type", None)
        meta.pop("reason_code", None)
        case.workflow_metadata = meta
        case.status = "classified"

        message_id = str(uuid4())

        await self._cases.add_timeline(
            case_id=case.id,
            event_type="gl_period_override",
            from_status="on_hold",
            to_status="classified",
            actor=poster,
            description=f"GL period override — requeued for posting ({reason})",
            metadata={"period_id": str(period.id), "queue_message_id": message_id},
            actor_user_id=user.user_id,
        )

        await self._activity.log(
            FinanceActivityLogCreate(
                actor_type="manager",
                actor_name=poster,
                action="gl_period_override_authorized",
                summary=f"[{case.case_number}] Authorized override post to closed period",
                case_id=case.id,
                metadata={
                    "period_id": str(period.id),
                    "override_reason": reason,
                    "authorized_by": poster,
                    "user_id": str(user.user_id),
                },
            )
        )

        await self._session.commit()

        case_id = case.id
        case_type = case.type
        case_number = case.case_number
        email_id = case.email_id
        priority = case.priority or "medium"
        stp_eligible = bool(case.stp_eligible)
        confidence_score = float(case.confidence_score or 0)

        await enqueue_accounts(
            case_id=case_id,
            case_type=case_type,
            case_number=case_number,
            email_id=email_id,
            priority=priority,
            stp_eligible=stp_eligible,
            confidence_score=confidence_score,
            source="gl-period-override",
            gl_period_override=True,
            gl_period_override_reason=reason,
            gl_period_posted_by=poster,
            message_id=message_id,
        )

        return {
            "case_id": str(case_id),
            "period_id": str(period.id),
            "message_id": message_id,
            "status": "requeued",
        }


def date_from_period(period: AccountingPeriod):
    from datetime import date

    return date(period.period_year, period.period_month, 1)
