"""Vendor suggestion merge and ranking."""

import pytest
from pydantic import ValidationError

from app.schemas.vendor_suggestion import VendorSuggestionQuery, VendorSuggestionResponse
from app.services.vendor_suggestions import merge_vendor_suggestions


def test_vendor_suggestions_merges_sources() -> None:
    merged = merge_vendor_suggestions(
        [("ACRA", "supplier", "billing@acra.gov.sg"), ("Beta Corp", "supplier", None)],
        ["OpenAI, LLC", "ACRA", "Anthropic, PBC"],
        limit=10,
    )
    names = [row.name for row in merged]
    assert names == ["ACRA", "Beta Corp", "OpenAI, LLC", "Anthropic, PBC"]
    acra = next(row for row in merged if row.name == "ACRA")
    assert acra.source == "counterparty"
    assert acra.counterparty_type == "supplier"
    assert acra.email == "billing@acra.gov.sg"
    openai = next(row for row in merged if row.name == "OpenAI, LLC")
    assert openai.source == "case_history"
    assert openai.counterparty_type is None
    assert openai.email is None


def test_vendor_suggestions_counterparty_ranked_first() -> None:
    merged = merge_vendor_suggestions(
        [("Shared Vendor", "employee", "emp@example.com")],
        ["Shared Vendor", "History Only"],
        limit=10,
    )
    assert [row.name for row in merged] == ["Shared Vendor", "History Only"]
    assert merged[0].source == "counterparty"
    assert merged[0].counterparty_type == "employee"
    assert merged[0].email == "emp@example.com"
    assert merged[1].source == "case_history"


def test_vendor_suggestions_deduplicates_case_insensitive() -> None:
    merged = merge_vendor_suggestions(
        [("Acme Corp", "supplier", None)],
        ["acme corp", "ACME CORP", "Other Vendor"],
        limit=10,
    )
    assert [row.name for row in merged] == ["Acme Corp", "Other Vendor"]


def test_vendor_suggestions_respects_limit() -> None:
    merged = merge_vendor_suggestions(
        [("A", "supplier", None), ("B", "supplier", None)],
        ["C", "D", "E"],
        limit=3,
    )
    assert len(merged) == 3
    assert [row.name for row in merged] == ["A", "B", "C"]


def test_vendor_suggestions_min_2_chars() -> None:
    assert VendorSuggestionQuery(search="ab").search == "ab"
    with pytest.raises(ValidationError):
        VendorSuggestionQuery(search="a")
