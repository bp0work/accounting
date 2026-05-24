"""Internal scheduler jobs — `05` §19."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.exceptions import AppHTTPException
from app.schemas.executive_mail import FinanceDailyLogJobRequest, FinanceDailyLogJobResponse
from app.services.finance_daily_log_service import FinanceDailyLogService

router = APIRouter(prefix="/internal/jobs", tags=["Internal Jobs"])


def _verify_cron_token(authorization: str | None = Header(default=None)) -> None:
    token = get_settings().internal_cron_token
    if not token:
        raise AppHTTPException(503, "CRON_NOT_CONFIGURED", "FINANCE_INTERNAL_CRON__TOKEN not set")
    if not authorization or not authorization.startswith("Bearer "):
        raise AppHTTPException(401, "INVALID_CRON_TOKEN", "Missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != token:
        raise AppHTTPException(401, "INVALID_CRON_TOKEN", "Invalid cron token")


@router.post("/finance-daily-log", response_model=FinanceDailyLogJobResponse)
async def finance_daily_log(
    body: FinanceDailyLogJobRequest | None = None,
    _: None = Depends(_verify_cron_token),
    session: AsyncSession = Depends(get_db_session),
) -> FinanceDailyLogJobResponse:
    req = body or FinanceDailyLogJobRequest()
    service = FinanceDailyLogService(session)
    return await service.run_job(business_date=req.business_date, force=req.force)


@router.post("/flush-outbound-mail")
async def flush_outbound_mail(
    _: None = Depends(_verify_cron_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Send approved rows in pending_outbound_emails (catch-up after SMTP enable)."""
    from app.services.outbound_mail_service import OutboundMailService

    sent = await OutboundMailService(session).flush_approved()
    await session.commit()
    return {"sent": sent}
