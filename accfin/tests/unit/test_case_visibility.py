"""Unit tests — case visibility helpers."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.models.case import Case
from app.services.case_visibility import (
    assignee_action_by,
    case_action_by,
    case_status_group,
    case_status_group_label,
    case_status_label,
    case_submitted_by,
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


def test_classified_ignores_stale_processing_metadata():
    case = _case(
        status="classified",
        workflow_metadata={"current_stage": "processing"},
    )
    assert case_status_group(case) == "processing"
    assert case_status_group_label(case) == "Processing"
    assert case_status_label(case) == "Waiting for worker"
    assert processing_stage(case) == "classified"


def test_case_rejected_ignores_stale_processing_metadata():
    case = _case(
        status="case_rejected",
        workflow_metadata={
            "current_stage": "processing",
            "error_reason": "Duplicate invoice",
        },
    )
    assert case_status_group(case) == "rejected"
    assert case_status_group_label(case) == "Rejected"
    assert case_status_label(case) == "Case rejected"
    assert processing_stage(case) == "case_rejected"
    assert error_reason(case) == "Duplicate invoice"


def test_processing_uses_parsing_step_when_active():
    case = _case(
        status="processing",
        workflow_metadata={"current_stage": "parsing"},
    )
    assert case_status_group(case) == "processing"
    assert case_status_label(case) == "Parsing document"


def test_status_reason_for_manual_review():
    case = _case(status="manual_review", workflow_metadata={"reason": "Empty extraction"})
    assert status_reason(case) == "Empty extraction"


def test_status_reason_includes_missing_fields_and_confidence():
    case = _case(
        status="manual_review",
        workflow_metadata={
            "missing_fields": ["document_number", "document_date"],
            "extraction_confidence": 0.62,
        },
    )
    assert status_reason(case) == (
        "Missing fields: document_number, document_date · Extraction confidence: 0.62"
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
                "document_number": "R-123",
            }
        },
    )
    assert (
        client_vendor_name(case)
        == "Accounting and Corporate Regulatory Authority"
    )


def test_pending_confirmation_state_is_processing():
    case = _case(status="pending_confirmation", workflow_metadata={})
    assert case_status_group(case) == "processing"
    assert case_status_group_label(case) == "Processing"
    assert case_status_label(case) == "Awaiting parsing confirmation"


def test_on_hold_pending_escalation_status_label():
    case = _case(
        status="on_hold",
        workflow_metadata={"escalation_pending": True, "escalation_id": "esc-1"},
    )
    assert case_status_label(case) == "On hold — action required"


def test_pending_approval_state_is_awaiting_approval():
    case = _case(status="pending_approval", workflow_metadata={})
    assert case_status_group(case) == "approval"
    assert case_status_group_label(case) == "Awaiting approval"


def test_posted_state_is_completed():
    case = _case(status="posted", workflow_metadata={})
    assert case_status_group(case) == "completed"
    assert case_status_group_label(case) == "Completed"


def test_rejected_status_not_grouped_as_attention():
    case = _case(status="rejected", workflow_metadata={})
    assert case_status_group(case) == "rejected"
    assert case_status_group_label(case) == "Rejected"


def test_action_by_processing_is_blank():
    case = _case(status="classified", workflow_metadata={})
    assert case_action_by(case) is None


def test_action_by_manual_review_is_acc():
    case = _case(status="manual_review", workflow_metadata={})
    assert case_action_by(case) == "ACC"


def test_assignee_finance_manager_is_acc_not_cfo():
    user = MagicMock()
    user.display_name = "Finance Manager"
    user.role.name = "finance_manager"
    assert assignee_action_by(user) == "ACC"


def test_assignee_finance_director_is_cfo():
    user = MagicMock()
    user.display_name = "Finance Director"
    user.role.name = "finance_director"
    assert assignee_action_by(user) == "CFO"


def test_action_by_tier2_approval_is_acc():
    case = _case(status="pending_approval", current_approval_tier=2, workflow_metadata={})
    assert case_action_by(case) == "ACC"


def test_action_by_tier3_approval_is_cfo():
    case = _case(status="pending_approval", current_approval_tier=3, workflow_metadata={})
    assert case_action_by(case) == "CFO"


def test_action_by_binding_escalation_is_cfo():
    case = _case(
        status="pending_approval",
        current_approval_tier=2,
        workflow_metadata={"binding_escalated_to_cfo": True},
    )
    assert case_action_by(case) == "CFO"


def test_action_by_completed_is_blank():
    case = _case(status="posted", workflow_metadata={})
    assert case_action_by(case) is None


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


def test_submitted_by_prefers_from_name():
    case = _case(
        classification_metadata={"from_address": "vendor@example.com"},
    )
    assert (
        case_submitted_by(
            case,
            from_name="Jane Vendor",
            from_address="vendor@example.com",
        )
        == "Jane Vendor"
    )


def test_submitted_by_falls_back_to_email():
    case = _case(classification_metadata={})
    assert (
        case_submitted_by(case, from_name=None, from_address="acc@example.com")
        == "acc@example.com"
    )


def test_submitted_by_workflow_metadata_fallback():
    case = _case(workflow_metadata={"submitted_by": "ops@example.com"})
    assert case_submitted_by(case) == "ops@example.com"
