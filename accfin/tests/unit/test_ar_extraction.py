"""AR extraction routing and Hermes stubs — `17` §4.5."""

from decimal import Decimal
from uuid import UUID

from agents.hermes.extract import (
    check_duplicate_stub,
    extract_invoice_stub,
    extract_payment_advice_stub,
    generate_soa_stub,
)
from app.schemas.hermes import (
    CheckDuplicateRequest,
    ExtractInvoiceRequest,
    ExtractPaymentAdviceRequest,
    ExtractedInvoice,
    GenerateSOARequest,
    RecentCase,
)
from workers.ar.extraction import evaluate_extraction_path, has_critical_missing


def test_evaluate_stp_posted():
    assert (
        evaluate_extraction_path(
            case_type="ar_invoice",
            confidence=0.95,
            missing_fields=[],
            stp_eligible=True,
            risk_flags=[],
        )
        == "posted"
    )


def test_evaluate_manual_on_critical_missing():
    assert (
        evaluate_extraction_path(
            case_type="ar_invoice",
            confidence=0.95,
            missing_fields=["document_number"],
            stp_eligible=True,
            risk_flags=[],
        )
        == "manual_review"
    )


def test_extract_invoice_stub_parses_subject():
    resp = extract_invoice_stub(
        ExtractInvoiceRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000001"),
            extracted_text="Invoice INV-555 Total: 1,250.00",
            supplier_hint="Acme Corp",
        )
    )
    assert resp.output is not None
    assert resp.output.document_number == "INV-555"
    assert resp.confidence_score >= 0.70


def test_check_duplicate_detects_match():
    resp = check_duplicate_stub(
        CheckDuplicateRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000002"),
            extracted_invoice=ExtractedInvoice(
                document_number="INV-1", total_amount="100.00", currency="SGD"
            ),
            recent_cases=[
                RecentCase(
                    case_id=UUID("00000000-0000-0000-0000-000000000003"),
                    case_number="CAS-1",
                    document_number="INV-1",
                    total_amount="100.00",
                )
            ],
        )
    )
    assert resp.output is not None
    assert resp.output.is_duplicate is True


def test_payment_advice_stub():
    resp = extract_payment_advice_stub(
        ExtractPaymentAdviceRequest(
            case_id=UUID("00000000-0000-0000-0000-000000000004"),
            extracted_text="Payment advice TT-99 Total: 500.00 for Invoice INV-9",
            customer_hint="Customer Ltd",
        )
    )
    assert resp.output is not None
    assert resp.output.payment_amount is not None


def test_soa_stub():
    resp = generate_soa_stub(
        GenerateSOARequest(
            case_id=UUID("00000000-0000-0000-0000-000000000005"),
            counterparty_name="Customer Ltd",
            open_invoices=[],
        )
    )
    assert resp.output is not None
    assert "Statement of Account" in resp.output.soa_text


def test_critical_missing_payment_advice():
    assert has_critical_missing("ar_payment_advice", ["payment_amount"])
