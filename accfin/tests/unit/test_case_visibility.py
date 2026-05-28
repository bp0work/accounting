"""Unit tests — case visibility helpers."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.models.case import Case
from app.services.case_visibility import (
    client_vendor_name,
    error_reason,
    processing_stage,
    status_reason,
)


def _case(**kwargs):
    c = MagicMock()
    c.status = kwargs.get("status", "exception")
    c.workflow_metadata = kwargs.get("workflow_metadata", {})
    c.current_approval_tier = kwargs.get("current_approval_tier")
    c.timeline = kwargs.get("timeline", [])
    c.updated_at = datetime.now(UTC)
    c.created_at = datetime.now(UTC)
    return c


def test_error_reason_from_workflow_metadata():
    case = _case(
        status="exception",
        workflow_metadata={"error_message": "Hermes timeout", "error_type": "HERMES_ERROR"},
    )
    assert error_reason(case) == "Hermes timeout"


def test_processing_stage_from_status():
    case = _case(status="classified", workflow_metadata={})
    assert processing_stage(case) == "classified"


def test_processing_stage_on_hold_hermes_not_classified():
    case = _case(
        status="on_hold",
        workflow_metadata={
            "current_stage": "classification",
            "reason_code": "HERMES_TIMEOUT",
        },
    )
    assert processing_stage(case) == "exception"


def test_status_reason_for_manual_review():
    case = _case(status="manual_review", workflow_metadata={"reason": "Empty extraction"})
    assert status_reason(case) == "Empty extraction"


def test_status_reason_includes_missing_fields_and_confidence():
    case = _case(
        status="manual_review",
        workflow_metadata={
            "missing_fields": ["invoice_number", "invoice_date"],
            "extraction_confidence": 0.62,
        },
    )
    assert status_reason(case) == (
        "Missing fields: invoice_number, invoice_date · Extraction confidence: 0.62"
    )


def test_client_vendor_name_ap_uses_extracted_vendor():
    case = Case(
        case_number="CAS-TEST-1",
        type="ap_invoice",
        status="manual_review",
        subject="ACRA receipt",
        counterparty_name="Marc Michelmann",
        amount_currency="SGD",
        workflow_metadata={
            "extracted_fields": {
                "vendor_name": "Accounting and Corporate Regulatory Authority",
                "invoice_number": "R-123",
            }
        },
    )
    assert (
        client_vendor_name(case)
        == "Accounting and Corporate Regulatory Authority"
    )


def test_client_vendor_name_ap_falls_back_to_counterparty():
    case = Case(
        case_number="CAS-TEST-2",
        type="ap_invoice",
        status="processing",
        subject="Invoice",
        counterparty_name="Acme Pte Ltd",
        amount_currency="SGD",
        workflow_metadata={},
    )
    assert client_vendor_name(case) == "Acme Pte Ltd"
