"""Journal entry approval detail for Finance UI case detail."""

from decimal import Decimal

from app.policies.binding_authority import BindingAuthorityThresholds
from app.schemas.journal_entry import JournalEntryApprovalDetail
from app.services.case_journal_approval import (
    _detail_from_metadata,
    _document_type_label,
    _stored_lines_usable,
    _tier_label,
)
from app.schemas.journal_entry import JournalEntryLineDetail


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
            "document_number": "ACRA250424004470",
            "document_date": "24 Apr 2025",
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


def test_stored_lines_usable_requires_account_id() -> None:
    assert _stored_lines_usable([]) is False
    assert (
        _stored_lines_usable(
            [
                JournalEntryLineDetail(
                    line_number=1,
                    account_id="00000000-0000-0000-0000-000000000001",
                    account_code="5010",
                    debit="1.00",
                )
            ]
        )
        is True
    )
    assert (
        _stored_lines_usable(
            [
                JournalEntryLineDetail(
                    line_number=1,
                    account_id="",
                    account_code="5010",
                    debit="1.00",
                )
            ]
        )
        is False
    )
