"""Case attachment listing with Wasabi pre-signed download URLs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.models.case import CaseAttachment
from app.models.mail import EmailAttachment
from app.repositories.case import CaseRepository
from app.schemas.case_attachment import CaseAttachmentItem
from app.services.wasabi_archive import WasabiArchiveService
from fastapi import status

PRESIGN_EXPIRY_SECONDS = 3600


class CaseAttachmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._wasabi = WasabiArchiveService(session)

    async def list_for_case(self, case_id: UUID) -> list[CaseAttachmentItem]:
        case = await self._cases.get(case_id)
        if case is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Case not found"
            )

        items: list[CaseAttachmentItem] = []
        if case.email_id:
            result = await self._session.execute(
                select(EmailAttachment)
                .where(EmailAttachment.email_id == case.email_id)
                .order_by(EmailAttachment.created_at.asc())
            )
            for row in result.scalars().all():
                items.append(await self._item_from_email_attachment(row))

        result = await self._session.execute(
            select(CaseAttachment)
            .where(CaseAttachment.case_id == case_id)
            .order_by(CaseAttachment.created_at.asc())
        )
        for row in result.scalars().all():
            items.append(self._item_from_case_attachment(row))

        return items

    async def _item_from_email_attachment(self, row: EmailAttachment) -> CaseAttachmentItem:
        download_url = None
        if row.wasabi_archive_path:
            download_url = await self._wasabi.presigned_download_url(
                object_key=row.wasabi_archive_path,
                expires=PRESIGN_EXPIRY_SECONDS,
            )
        return CaseAttachmentItem(
            id=row.id,
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=row.file_size,
            source="email",
            download_url=download_url,
            expires_in_seconds=PRESIGN_EXPIRY_SECONDS if download_url else None,
        )

    @staticmethod
    def _item_from_case_attachment(row: CaseAttachment) -> CaseAttachmentItem:
        return CaseAttachmentItem(
            id=row.id,
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            source="case_upload",
            download_url=None,
            expires_in_seconds=None,
        )
