"""Finance daily activity digest — `05` §19.1, `17` §10.7."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.executive_mail import FinanceActivityLogRepository
from app.repositories.system_settings import SystemSettingsRepository
from app.schemas.executive_mail import FinanceDailyLogJobResponse
from app.services.outbound_mail_service import OutboundMailService


class FinanceDailyLogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._log_repo = FinanceActivityLogRepository(session)
        self._settings = SystemSettingsRepository(session)
        self._cfg = get_settings()

    def _business_date_today(self) -> date:
        tz = ZoneInfo(self._cfg.daily_log_timezone)
        return datetime.now(tz).date()

    async def run_job(
        self,
        *,
        business_date: date | None = None,
        force: bool = False,
    ) -> FinanceDailyLogJobResponse:
        biz = business_date or self._business_date_today()
        last_raw = await self._settings.get_value("last_finance_log_sent_at", "")
        if last_raw and not force:
            try:
                last_dt = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
                last_biz = last_dt.astimezone(ZoneInfo(self._cfg.daily_log_timezone)).date()
                if last_biz == biz:
                    return FinanceDailyLogJobResponse(
                        status="skipped",
                        business_date=biz,
                        reason="already_sent",
                        last_sent_at=last_dt,
                    )
            except ValueError:
                pass

        rows = await self._log_repo.list_for_business_date(biz)
        csv_bytes = self._build_csv(rows)
        filename = f"finance_daily_{biz.isoformat()}.csv"
        wasabi_key = f"{self._cfg.wasabi_prefix_logs.rstrip('/')}/{filename}".lstrip("/")
        local_path = self._write_local(csv_bytes, filename)

        sent_at = datetime.now(UTC)
        message = None
        smtp_id = None

        mailbox_summary = self._mailbox_summary(rows)
        if self._cfg.smtp_configured:
            outbound = OutboundMailService(self._session)
            smtp_id = await outbound.send_daily_log(
                business_date=biz,
                recipient=self._cfg.daily_log_recipient,
                csv_bytes=csv_bytes,
                filename=filename,
                row_count=len(rows),
                mailbox_summary=mailbox_summary,
            )
            if smtp_id is None:
                message = f"SMTP send failed; CSV archived at {local_path}"
        elif not self._cfg.smtp_enabled:
            message = f"SMTP disabled; CSV archived at {local_path}"
        else:
            message = f"SMTP host not configured; CSV archived at {local_path}"

        await self._settings.set_value("last_finance_log_sent_at", sent_at.isoformat())

        return FinanceDailyLogJobResponse(
            status="sent",
            business_date=biz,
            recipient=self._cfg.daily_log_recipient,
            row_count=len(rows),
            smtp_message_id=smtp_id,
            sent_at=sent_at,
            wasabi_log_path=wasabi_key,
            attachment_filename=filename,
            message=message,
        )

    def _build_csv(self, rows) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "occurred_at",
                "business_date",
                "mailbox_id",
                "case_id",
                "email_id",
                "actor_type",
                "actor_name",
                "action",
                "summary",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.occurred_at.isoformat() if row.occurred_at else "",
                    row.business_date.isoformat() if row.business_date else "",
                    str(row.mailbox_id) if row.mailbox_id else "",
                    str(row.case_id) if row.case_id else "",
                    str(row.email_id) if row.email_id else "",
                    row.actor_type,
                    row.actor_name or "",
                    row.action,
                    row.summary,
                ]
            )
        text = buf.getvalue()
        if self._cfg.daily_log_csv_utf8_bom:
            return ("\ufeff" + text).encode("utf-8")
        return text.encode("utf-8")

    def _mailbox_summary(self, rows) -> list[dict]:
        counts: dict[str, int] = {}
        for row in rows:
            key = str(row.mailbox_id) if row.mailbox_id else "unknown"
            counts[key] = counts.get(key, 0) + 1
        return [{"mailbox": mailbox, "count": count} for mailbox, count in sorted(counts.items())]

    def _write_local(self, content: bytes, filename: str) -> Path:
        base = Path(self._cfg.attachment_storage_path) / "logs"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            base = Path.cwd() / ".finance_logs"
            base.mkdir(parents=True, exist_ok=True)
        path = base / filename
        path.write_bytes(content)
        return path
