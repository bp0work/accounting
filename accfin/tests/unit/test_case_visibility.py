"""Unit tests — case visibility helpers."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.services.case_visibility import error_reason, processing_stage, status_reason


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
