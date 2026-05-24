"""Wasabi long-term attachment archive — `06` §7.5, `14` §2.9."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.mail import EmailAttachment
from app.services.mail.storage import attachment_dir

logger = logging.getLogger(__name__)


def build_transaction_archive_key(
    *,
    case_number: str,
    filename: str,
    prefix_transactions: str = "transactions/",
) -> str:
    """Object key: ``transactions/{case_number}/{filename}`` (`06` §7.5)."""
    safe_name = Path(filename).name
    prefix = prefix_transactions.rstrip("/") + "/"
    return f"{prefix}{case_number}/{safe_name}"


def resolve_local_attachment_path(
    attachment: EmailAttachment,
    *,
    attachment_storage_path: str | None = None,
) -> Path:
    """Resolve hot-store path: ``{ATTACHMENT_STORAGE_PATH}/{email_id}/{filename}``."""
    base = Path(attachment_storage_path or get_settings().attachment_storage_path)
    if attachment.storage_path:
        candidate = base / attachment.storage_path
        if candidate.is_file():
            return candidate
    return attachment_dir(attachment.email_id) / Path(attachment.filename).name


class WasabiArchiveService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def _s3_client(self):
        return boto3.client(
            "s3",
            endpoint_url=self._settings.wasabi_endpoint_url,
            aws_access_key_id=self._settings.wasabi_access_key_id,
            aws_secret_access_key=self._settings.wasabi_secret_access_key,
            region_name=self._settings.wasabi_region,
            config=Config(signature_version="s3v4"),
        )

    def _upload_file_sync(self, *, local_path: Path, object_key: str, content_type: str) -> None:
        extra_args = {"ContentType": content_type} if content_type else None
        client = self._s3_client()
        if extra_args:
            client.upload_file(
                str(local_path),
                self._settings.wasabi_bucket,
                object_key,
                ExtraArgs=extra_args,
            )
        else:
            client.upload_file(str(local_path), self._settings.wasabi_bucket, object_key)

    async def archive_email_attachments(
        self,
        *,
        case_number: str,
        email_id: UUID,
    ) -> dict[str, int | str]:
        if not self._settings.wasabi_archive_on_intake:
            return {"archived": 0, "skipped": "disabled"}

        if not self._settings.wasabi_configured:
            logger.warning(
                "FINANCE_WASABI__ARCHIVE_ON_INTAKE=true but Wasabi credentials are missing"
            )
            return {"archived": 0, "skipped": "not_configured"}

        result = await self._session.execute(
            select(EmailAttachment).where(EmailAttachment.email_id == email_id)
        )
        attachments = list(result.scalars().all())
        archived = 0
        for attachment in attachments:
            if attachment.wasabi_archive_path:
                continue
            try:
                if await self._archive_one(case_number=case_number, attachment=attachment):
                    archived += 1
            except (BotoCoreError, ClientError, OSError) as exc:
                logger.exception(
                    "Wasabi archive failed for attachment %s (email %s): %s",
                    attachment.id,
                    email_id,
                    exc,
                )
        return {"archived": archived, "total": len(attachments)}

    async def _archive_one(self, *, case_number: str, attachment: EmailAttachment) -> bool:
        local_path = resolve_local_attachment_path(
            attachment,
            attachment_storage_path=self._settings.attachment_storage_path,
        )
        if not local_path.is_file():
            logger.warning(
                "Attachment file missing for Wasabi archive: %s (attachment %s)",
                local_path,
                attachment.id,
            )
            return False

        object_key = build_transaction_archive_key(
            case_number=case_number,
            filename=attachment.filename,
            prefix_transactions=self._settings.wasabi_prefix_transactions,
        )
        await asyncio.to_thread(
            self._upload_file_sync,
            local_path=local_path,
            object_key=object_key,
            content_type=attachment.mime_type,
        )
        attachment.wasabi_archive_path = object_key
        await self._session.flush()
        logger.info(
            "Archived attachment %s to s3://%s/%s",
            attachment.id,
            self._settings.wasabi_bucket,
            object_key,
        )
        return True
