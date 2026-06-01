"""Parsing confirmation field normalization."""

from workers.common.parsing_confirmation import normalize_extracted_fields


def test_normalize_extracted_fields_includes_gl_account_id_when_set() -> None:
    out = normalize_extracted_fields(
        {
            "document_type": "receipt",
            "vendor_name": "Cafe",
            "total_amount": "10.00",
            "currency": "SGD",
            "gl_account_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        }
    )
    assert out["gl_account_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_normalize_extracted_fields_gl_account_id_null_when_missing() -> None:
    out = normalize_extracted_fields(
        {
            "document_type": "receipt",
            "vendor_name": "Cafe",
            "total_amount": "10.00",
            "currency": "SGD",
        }
    )
    assert "gl_account_id" in out
    assert out["gl_account_id"] is None
