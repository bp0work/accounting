"""Mail Gateway API routes — `21_openapi.yaml` /mail/*."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.core.redis_client import get_redis
from app.repositories.mail import MailRepository
from app.schemas.auth import TokenData
from app.schemas.mail import (
    EmailListResponse,
    EmailMessageResponse,
    MailGatewayStatusResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/mail", tags=["Mail Gateway"])


@router.get("/status", response_model=MailGatewayStatusResponse)
async def mail_status(
    _user: TokenData = Depends(require_permission("mail:read")),
    session: AsyncSession = Depends(get_db_session),
) -> MailGatewayStatusResponse:
    repo = MailRepository(session)
    mailboxes = await repo.list_mailboxes()
    executive = [m for m in mailboxes if m.mailbox_mode == "executive_agent" and m.is_active]
    managers = [m for m in mailboxes if m.mailbox_mode == "manager_human"]
    counts = await repo.count_emails_by_status()
    redis = get_redis()
    depth = await redis.llen(get_settings().intake_queue_name)
    return MailGatewayStatusResponse(
        poll_enabled=get_settings().mail_poll_enabled,
        executive_mailboxes_active=len(executive),
        manager_mailboxes_configured=len(managers),
        emails_by_status=counts,
        intake_queue_depth=depth,
    )


@router.get("", response_model=EmailListResponse)
async def list_mail(
    limit: int = Query(default=50, ge=1, le=100),
    _user: TokenData = Depends(require_permission("mail:read")),
    session: AsyncSession = Depends(get_db_session),
) -> EmailListResponse:
    repo = MailRepository(session)
    emails = await repo.list_emails(limit=limit + 1)
    has_more = len(emails) > limit
    page = emails[:limit]
    return EmailListResponse(
        data=[EmailMessageResponse.model_validate(e) for e in page],
        pagination=PaginationMeta(has_more=has_more),
    )


@router.get("/{email_id}", response_model=EmailMessageResponse)
async def get_mail(
    email_id: UUID,
    _user: TokenData = Depends(require_permission("mail:read")),
    session: AsyncSession = Depends(get_db_session),
) -> EmailMessageResponse:
    repo = MailRepository(session)
    email = await repo.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Email not found"}})
    return EmailMessageResponse.model_validate(email)


@router.get("/{email_id}/attachments/{attachment_id}")
async def download_attachment(
    email_id: UUID,
    attachment_id: UUID,
    _user: TokenData = Depends(require_permission("mail:read")),
    session: AsyncSession = Depends(get_db_session),
):
    repo = MailRepository(session)
    email = await repo.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Email not found"}})
    attachment = next((a for a in email.attachments if a.id == attachment_id), None)
    if attachment is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Attachment not found"}})
    base = Path(get_settings().attachment_storage_path)
    path = base / attachment.storage_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "File missing on disk"}})
    return FileResponse(path, filename=attachment.filename, media_type=attachment.mime_type)


@router.get("/{email_id}/duplicates")
async def list_duplicates(
    email_id: UUID,
    _user: TokenData = Depends(require_permission("mail:read")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    repo = MailRepository(session)
    duplicates = await repo.get_duplicates_for(email_id)
    return {"data": [EmailMessageResponse.model_validate(d) for d in duplicates]}
