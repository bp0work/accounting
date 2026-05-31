"""Vendor extraction hint prompt formatting."""

from uuid import uuid4

from app.models.vendor_extraction_hint import VendorExtractionHint
from app.services.vendor_extraction_hints import format_vendor_hints_prompt


def test_format_vendor_hints_prompt_includes_label_and_date_format() -> None:
    hint = VendorExtractionHint(
        id=uuid4(),
        tenant_id=uuid4(),
        vendor_name="ACRA",
        field_name="document_date",
        field_label="Date and time",
        field_location="header",
        example_value="24 Apr 2025 07:42 PM",
        date_format="DD Mon YYYY HH:MM AM/PM",
        is_active=True,
        created_by=None,
    )
    block = format_vendor_hints_prompt([hint], vendor_name="ACRA")
    assert "For vendor ACRA" in block
    assert "document_date is labelled 'Date and time'" in block
    assert "24 Apr 2025 07:42 PM" in block
    assert "Parse document_date using format DD Mon YYYY HH:MM AM/PM" in block
