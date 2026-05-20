"""AP extraction routing, expense account, PO match stub — `17` §5."""

from decimal import Decimal
from uuid import UUID

from agents.hermes.extract import extract_invoice_stub, validate_po_match_stub
from app.schemas.hermes import ExtractedInvoice, ExtractInvoiceRequest, ValidatePOMatchRequest
from workers.ap.extraction import (
    compute_ap_invoice_risk_flags,
    evaluate_extraction_path,
    has_critical_missing,
    resolve_expense_account_code,
)


def test_evaluate_stp_posted_ap():
    assert (
        evaluate_extraction_path(
            case_type="ap_invoice",
            confidence=0.95,
            missing_fields=[],
            stp_eligible=True,
            risk_flags=[],
        )
        == "posted"
    )


def test_evaluate_manual_on_vendor_missing():
    assert (
        evaluate_extraction_path(
            case_type="ap_invoice",
            confidence=0.95,
            missing_fields=["vendor_name"],
            stp_eligible=True,
            risk_flags=[],
        )
        == "manual_review"
    )


def test_resolve_expense_from_line_items():
    assert (
        resolve_expense_account_code([{"account_code": "6100", "description": "Freight"}])
        == "6100"
    )


def test_resolve_expense_default():
    assert resolve_expense_account_code(None) == "5500"


def test_ap_risk_flags_po_mismatch():
    flags = compute_ap_invoice_risk_flags(
        duplicate_score=0.0,
        amount=Decimal("1000"),
        po_not_found=False,
        po_mismatch=True,
        warnings=[],
    )
    assert "po_amount_mismatch" in flags


def test_extract_invoice_parses_po_reference():
    resp = extract_invoice_stub(
        ExtractInvoiceRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000010"),
            extracted_text="Invoice INV-AP-1 PO PO-SEED-99 Total: 5,000.00",
            supplier_hint="Supplier Ltd",
        )
    )
    assert resp.output is not None
    assert resp.output.po_reference == "PO-SEED-99"


def test_validate_po_match_match():
    resp = validate_po_match_stub(
        ValidatePOMatchRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000011"),
            extracted_invoice=ExtractedInvoice(
                total_amount="5000.00", currency="SGD", vendor_name="Supplier"
            ),
            po_data={"total_amount": "5000.00", "currency": "SGD"},
        )
    )
    assert resp.output is not None
    assert resp.output.match_status == "match"


def test_validate_po_match_mismatch():
    resp = validate_po_match_stub(
        ValidatePOMatchRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000012"),
            extracted_invoice=ExtractedInvoice(total_amount="100.00", currency="SGD"),
            po_data={"total_amount": "5000.00", "currency": "SGD"},
        )
    )
    assert resp.output is not None
    assert resp.output.match_status == "mismatch"


def test_critical_missing_po_validation():
    assert has_critical_missing("ap_po_validation", ["po_reference"])
