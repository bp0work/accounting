"""Finance oversight: dashboard and CSV export."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.case import Case
from app.models.mail import Email


@pytest.mark.integration
async def test_cases_dashboard_and_export(
    async_client: AsyncClient, db_session, auth_headers
) -> None:
    now = datetime.now(UTC)
    email = Email(
        message_id=f"<exp-{uuid4().hex}@test>",
        mailbox_address="accap.mmlogistix@bp0.work",
        from_address="vendor@acme.sg",
        to_addresses=["accap.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject="Export test invoice",
        status="classified",
        received_at=now,
    )
    db_session.add(email)
    await db_session.flush()

    case = Case(
        case_number=f"CAS-EXP-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="processing",
        subject="Export test case",
        counterparty_name="Marc Michelmann",
        amount_value=Decimal("99.50"),
        amount_currency="SGD",
        email_id=email.id,
        created_at=now,
        sla_deadline=now - timedelta(hours=1),
        sla_status="breached",
        workflow_metadata={
            "extracted_fields": {
                "vendor_name": "Accounting and Corporate Regulatory Authority",
                "document_number": "DOC-EXPORT-001",
            }
        },
    )
    db_session.add(case)
    await db_session.commit()

    dash = await async_client.get("/api/cases/dashboard", headers=auth_headers)
    assert dash.status_code == 200
    body = dash.json()
    assert "queue_depths" in body
    assert "cases_by_status" in body
    assert body["overdue_count"] >= 1

    today = now.date().isoformat()
    export = await async_client.get(
        f"/api/cases/export?date_from={today}&date_to={today}",
        headers=auth_headers,
    )
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")
    assert "attachment" in export.headers.get("content-disposition", "")
    assert "Case Number" in export.text
    assert "Submitted By" in export.text
    assert "Document Number" in export.text
    assert "completed_at" not in export.text.split("\n")[0]
    assert case.case_number in export.text
    assert "DOC-EXPORT-001" in export.text
    assert "Marc Michelmann" in export.text

    listed = await async_client.get("/api/cases?limit=10", headers=auth_headers)
    assert listed.status_code == 200
    row = next((r for r in listed.json()["data"] if r["case_number"] == case.case_number), None)
    assert row is not None
    assert row["is_overdue"] is True
    assert row["processing_time_minutes"] is not None
    assert row["counterparty_name"] == "Marc Michelmann"
    assert row["client_vendor_name"] == "Accounting and Corporate Regulatory Authority"
    assert row["from_address"] == "vendor@acme.sg"
