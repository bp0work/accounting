"""GET /api/cases/{id}/attachments — pre-signed Wasabi download URLs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.case import Case
from app.models.mail import Email, EmailAttachment


@pytest.mark.integration
async def test_list_case_attachments_presigns_email_files(
    db_session,
    async_client: AsyncClient,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    email = Email(
        message_id=f"<attach-{uuid4().hex}@test>",
        mailbox_address="accap.mmlogistix@bp0.work",
        from_address="vendor@example.com",
        from_name="Vendor Co",
        to_addresses=["accap.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject="Invoice attached",
        body_text="See attachment",
        status="classified",
        received_at=now,
    )
    db_session.add(email)
    await db_session.flush()

    attachment = EmailAttachment(
        email_id=email.id,
        filename="invoice.pdf",
        file_size=1024,
        mime_type="application/pdf",
        storage_path=f"{email.id}/invoice.pdf",
        content_hash="abc123",
        wasabi_archive_path="transactions/CAS-ATTACH-1/invoice.pdf",
    )
    db_session.add(attachment)

    case = Case(
        case_number=f"CAS-ATTACH-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="classified",
        subject="Invoice attached",
        email_id=email.id,
        counterparty_name="Vendor Co",
    )
    db_session.add(case)
    await db_session.commit()

    async def fake_presign(*, object_key: str, expires: int = 3600) -> str | None:
        assert object_key == "transactions/CAS-ATTACH-1/invoice.pdf"
        assert expires == 3600
        return f"https://wasabi.test/{object_key}?exp={expires}"

    monkeypatch.setattr(
        "app.services.case_attachments.WasabiArchiveService.presigned_download_url",
        fake_presign,
    )

    response = await async_client.get(
        f"/api/cases/{case.id}/attachments",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert len(data) == 1
    row = data[0]
    assert row["filename"] == "invoice.pdf"
    assert row["source"] == "email"
    assert row["download_url"] == (
        "https://wasabi.test/transactions/CAS-ATTACH-1/invoice.pdf?exp=3600"
    )
    assert row["expires_in_seconds"] == 3600


@pytest.mark.integration
async def test_list_case_attachments_not_found(
    async_client: AsyncClient,
    auth_headers,
) -> None:
    response = await async_client.get(
        f"/api/cases/{uuid4()}/attachments",
        headers=auth_headers,
    )
    assert response.status_code == 404
