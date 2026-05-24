"""Wasabi attachment archive — `06` §7.5, `14` §2.9."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.mail import EmailAttachment
from app.services.wasabi_archive import (
    WasabiArchiveService,
    build_transaction_archive_key,
    resolve_local_attachment_path,
)


def test_build_transaction_archive_key():
    key = build_transaction_archive_key(
        case_number="CAS-20260520-0001",
        filename="invoice.pdf",
    )
    assert key == "transactions/CAS-20260520-0001/invoice.pdf"


def test_build_transaction_archive_key_sanitizes_path_segments():
    key = build_transaction_archive_key(
        case_number="CAS-20260520-0001",
        filename="../../etc/passwd",
    )
    assert key == "transactions/CAS-20260520-0001/passwd"


def test_resolve_local_attachment_path_from_storage_path(tmp_path):
    email_id = uuid.uuid4()
    rel = f"{email_id}/doc.pdf"
    local = tmp_path / rel
    local.parent.mkdir(parents=True)
    local.write_bytes(b"pdf")

    attachment = EmailAttachment(
        email_id=email_id,
        filename="doc.pdf",
        file_size=3,
        mime_type="application/pdf",
        storage_path=rel,
        content_hash="abc",
    )
    resolved = resolve_local_attachment_path(
        attachment, attachment_storage_path=str(tmp_path)
    )
    assert resolved == local


@pytest.mark.asyncio
async def test_archive_skips_when_disabled():
    settings = Settings(
        FINANCE_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        FINANCE_REDIS__PASSWORD="x",
        FINANCE_JWT__SECRET="secret",
        FINANCE_PRIVACY_ENCRYPTION_KEY="0" * 64,
        FINANCE_WASABI__ARCHIVE_ON_INTAKE=False,
    )
    session = AsyncMock()
    svc = WasabiArchiveService(session, settings=settings)
    result = await svc.archive_email_attachments(
        case_number="CAS-20260520-0001",
        email_id=uuid.uuid4(),
    )
    assert result == {"archived": 0, "skipped": "disabled"}
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_archive_uploads_and_updates_db(tmp_path):
    email_id = uuid.uuid4()
    rel = f"{email_id}/invoice.pdf"
    local = tmp_path / rel
    local.parent.mkdir(parents=True)
    local.write_bytes(b"%PDF-1.4")

    attachment = EmailAttachment(
        id=uuid.uuid4(),
        email_id=email_id,
        filename="invoice.pdf",
        file_size=8,
        mime_type="application/pdf",
        storage_path=rel,
        content_hash="deadbeef",
    )

    settings = Settings(
        FINANCE_DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        FINANCE_REDIS__PASSWORD="x",
        FINANCE_JWT__SECRET="secret",
        FINANCE_PRIVACY_ENCRYPTION_KEY="0" * 64,
        FINANCE_MAIL__ATTACHMENT_STORAGE_PATH=str(tmp_path),
        FINANCE_WASABI__ACCESS_KEY_ID="key",
        FINANCE_WASABI__SECRET_ACCESS_KEY="secret",
        FINANCE_WASABI__ARCHIVE_ON_INTAKE=True,
    )

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [attachment]
    session.execute = AsyncMock(return_value=result_mock)
    session.flush = AsyncMock()

    svc = WasabiArchiveService(session, settings=settings)
    with patch.object(svc, "_upload_file_sync") as upload_mock:
        outcome = await svc.archive_email_attachments(
            case_number="CAS-20260520-0001",
            email_id=email_id,
        )

    upload_mock.assert_called_once()
    assert upload_mock.call_args.kwargs["object_key"] == (
        "transactions/CAS-20260520-0001/invoice.pdf"
    )
    assert attachment.wasabi_archive_path == "transactions/CAS-20260520-0001/invoice.pdf"
    assert outcome == {"archived": 1, "total": 1}
    session.flush.assert_awaited()
