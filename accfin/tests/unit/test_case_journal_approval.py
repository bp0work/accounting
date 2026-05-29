"""Journal entry approval detail for Finance UI case detail."""

from decimal import Decimal

from app.policies.binding_authority import BindingAuthorityThresholds
from app.schemas.journal_entry import JournalEntryApprovalDetail
from app.services.case_journal_approval import (
    _detail_from_metadata,
    _document_type_label,
    _tier_label,
)


def test_tier2_label_matches_finance_ui_copy() -> None:
    th = BindingAuthorityThresholds.from_rules(None)
    label = _tier_label(2, th, "SGD")
    assert label == "Tier 2 (SGD 3,001 – 10,000)"


def test_document_type_label_invoice() -> None:
    assert _document_type_label("invoice") == "Invoice"


def test_detail_from_workflow_metadata() -> None:
    meta = {
        "journal_entry": {
            "vendor": "ACRA",
            "invoice_number": "ACRA250424004470",
            "invoice_date": "24 Apr 2025",
            "document_type": "Invoice",
            "amount_sgd": "15.00",
            "gst": "1.24",
            "total": "16.24",
            "debit_account": "Professional Fees",
            "credit_account": "Trade Creditors",
            "approval_tier_label": "Tier 2 (SGD 3,001 – 10,000)",
        }
    }
    detail = _detail_from_metadata(meta)
    assert isinstance(detail, JournalEntryApprovalDetail)
    assert detail.vendor == "ACRA"
    assert detail.total == "16.24"
