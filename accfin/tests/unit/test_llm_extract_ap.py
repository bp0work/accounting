"""AP invoice LLM extraction helpers — vendor, due date, field labels."""

from datetime import date

from agents.hermes.extract import extract_invoice_stub
from agents.hermes.llm_extract import _normalize_ap_due_date
from app.schemas.hermes import ExtractInvoiceRequest
from uuid import UUID


def test_normalize_ap_due_date_paid_receipt_uses_invoice_date():
    inv_date = date(2026, 5, 10)
    assert (
        _normalize_ap_due_date(
            inv_date,
            None,
            "ACRA Receipt no. R-123 Payment confirmed. Amount paid SGD 50.00",
        )
        == inv_date
    )


def test_normalize_ap_due_date_keeps_explicit_due_date():
    inv_date = date(2026, 5, 10)
    due = date(2026, 6, 10)
    assert (
        _normalize_ap_due_date(inv_date, due, "Invoice with Net 30 terms")
        == due
    )


def test_extract_stub_parses_receipt_number():
    resp = extract_invoice_stub(
        ExtractInvoiceRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000020"),
            extracted_text="Receipt no. ARN-998877 Total: 15.00",
            supplier_hint="Marc Michelmann",
        )
    )
    assert resp.output is not None
    assert resp.output.invoice_number == "ARN-998877"
