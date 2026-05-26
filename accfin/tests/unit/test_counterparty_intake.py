"""Unit tests for Phase 13 intake helpers — maps to UAT-013."""

from datetime import date
from decimal import Decimal

from app.services.counterparty_intake import _normalize_term_code, compute_due_date
from app.models.counterparty_master import PaymentTerm


def test_normalize_net30_variants() -> None:
    assert _normalize_term_code("Net 30") == "NET30"
    assert _normalize_term_code("NET30") == "NET30"
    assert _normalize_term_code("30 days") == "NET30"


def test_due_date_from_terms_when_not_on_document() -> None:
    term = PaymentTerm(
        code="NET30",
        label="Net 30",
        due_days=30,
        is_active=True,
    )
    inv_date = date(2026, 5, 1)
    due, source, warnings = compute_due_date(
        invoice_date=inv_date,
        extracted_due=None,
        term=term,
        document_total=Decimal("1000"),
    )
    assert due == date(2026, 5, 31)
    assert source == "payment_terms"
    assert warnings == []


def test_extracted_due_date_wins() -> None:
    term = PaymentTerm(code="NET30", label="Net 30", due_days=30, is_active=True)
    explicit = date(2026, 6, 15)
    due, source, _ = compute_due_date(
        invoice_date=date(2026, 5, 1),
        extracted_due=explicit,
        term=term,
        document_total=Decimal("100"),
    )
    assert due == explicit
    assert source == "extracted"
