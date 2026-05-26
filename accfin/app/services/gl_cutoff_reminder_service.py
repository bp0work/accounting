"""Send GL cutoff reminder emails — cron job `POST /api/internal/jobs/gl-cutoff-reminders`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.accounting_period import AccountingPeriod
from app.models.gl_cutoff_reminder import GlCutoffReminder
from app.models.mail import MailGatewayConfig
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.accounting_calendar import period_display_name, period_type_label
from app.services.finance_activity_log_service import FinanceActivityLogService
from app.services.outbound_mail_service import OutboundMailService

logger = logging.getLogger(__name__)

SENDER_EMAIL = "acc.mmlogistix@bp0.work"

FLAG_BY_DAYS = {
    7: "notify_7_days",
    3: "notify_3_days",
    1: "notify_1_day",
    0: "notify_on_date",
}


@dataclass
class GlCutoffReminderJobResult:
    periods_checked: int
    emails_sent: int
    skipped_smtp: bool


class GlCutoffReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._outbound = OutboundMailService(session)
        self._activity = FinanceActivityLogService(session)

    async def run(self) -> GlCutoffReminderJobResult:
        if not self._settings.smtp_configured:
            logger.warning("SMTP not configured; skipping GL cutoff reminders")
            return GlCutoffReminderJobResult(periods_checked=0, emails_sent=0, skipped_smtp=True)

        mailbox = await self._load_sender_mailbox()
        if mailbox is None:
            logger.warning("Sender mailbox %s not found", SENDER_EMAIL)
            return GlCutoffReminderJobResult(periods_checked=0, emails_sent=0, skipped_smtp=True)

        today = date.today()
        periods = (
            await self._session.execute(
                select(AccountingPeriod).where(AccountingPeriod.status.in_(("open", "review")))
            )
        ).scalars().all()

        recipients = (
            await self._session.execute(
                select(GlCutoffReminder).where(GlCutoffReminder.is_active.is_(True))
            )
        ).scalars().all()

        sent = 0
        for period in periods:
            days_until = (period.gl_cutoff_date - today).days
            if days_until not in FLAG_BY_DAYS:
                continue
            flag = FLAG_BY_DAYS[days_until]
            period_name = period_display_name(period.period_year, period.period_month)
            ptype = period_type_label(period.period_type)
            for rec in recipients:
                if rec.tenant_id != period.tenant_id:
                    continue
                if not getattr(rec, flag):
                    continue
                subject, body = self._compose_email(
                    days_until=days_until,
                    period_name=period_name,
                    period_type=ptype,
                    cutoff=period.gl_cutoff_date,
                    status=period.status,
                    reviewer=period.trial_balance_reviewer,
                )
                try:
                    await self._smtp.send_message(
                        from_address=mailbox.email_address,
                        from_name=mailbox.display_name or "mmlogistix Accounts",
                        username=mailbox.username,
                        password=password,
                        to_addresses=[rec.email],
                        subject=subject,
                        body_plain=body,
                    )
                    await self._activity.log(
                        FinanceActivityLogCreate(
                            actor_type="system",
                            actor_name="gl-cutoff-reminder",
                            action="gl_cutoff_reminder_sent",
                            summary=f"GL cutoff reminder ({days_until}d) → {rec.email} for {period_name}",
                            metadata={
                                "period_id": str(period.id),
                                "recipient_email": rec.email,
                                "days_until_cutoff": days_until,
                            },
                        )
                    )
                    sent += 1
                except Exception:
                    logger.exception(
                        "GL cutoff reminder failed period=%s recipient=%s",
                        period.id,
                        rec.email,
                    )

        await self._session.commit()
        return GlCutoffReminderJobResult(
            periods_checked=len(periods), emails_sent=sent, skipped_smtp=False
        )

    async def _load_sender_mailbox(self) -> MailGatewayConfig | None:
        result = await self._session.execute(
            select(MailGatewayConfig).where(
                MailGatewayConfig.email_address == SENDER_EMAIL,
                MailGatewayConfig.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

