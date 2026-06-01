"""Case CSV export columns — `0.14.75`."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.models.case import Case
from app.services.case_export import (
    CSV_HEADERS,
    _case_export_row,
    _document_number,
    _format_export_amount,
)


def test_export_headers() -> None:
    assert CSV_HEADERS == [
        "Case Number",
        "Submitted By",
        "Date Submitted",
        "Type",
        "Document Number",
        "Document Currency",
        "Document Amount",
        "Status",
    ]


def test_case_export_row_formats_date_and_extracted_fields() -> None:
    case = Case(
        case_number="CAS-2025-0001",
        type="expense_claim",
        status="posted",
        counterparty_name="Jane Employee",
        amount_value=Decimal("115.00"),
        amount_currency="SGD",
        created_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
        workflow_metadata={
            "extracted_fields": {"document_number": "INV-42", "vendor_name": "Acme"},
        },
    )
    row = _case_export_row(case)
    assert row[0] == "CAS-2025-0001"
    assert row[1] == "Jane Employee"
    assert row[2] == "15/03/2025"
    assert row[3] == "expense_claim"
    assert row[4] == "INV-42"
    assert row[5] == "SGD"
    assert row[6] == "115.00"  # Document Amount — always 2 dp
    assert row[7] == "posted"


def test_format_export_amount_two_decimals() -> None:
    assert _format_export_amount(Decimal("99.5")) == "99.50"
    assert _format_export_amount(None) == ""


def test_document_number_missing_metadata() -> None:
    case = Case(
        case_number=f"CAS-{uuid4().hex[:6]}",
        type="ap_invoice",
        status="processing",
    )
    assert _document_number(case) == ""
