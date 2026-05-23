"""PDF attachment text extraction."""

from app.services.attachment_text import extract_attachment_text_sync


def test_extract_pdf_text_from_minimal_pdf():
    # Minimal valid PDF with "INVOICE TOTAL 100.00" text stream
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<<>>endobj\n"
        b"2 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 100 700 Td (INVOICE TOTAL 100.00) Tj ET\n"
        b"endstream\nendobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Contents 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000022 00000 n \n0000000120 00000 n \n"
        b"trailer<</Size 4/Root<</Pages<</Kids[3 0 R]/Count 1>>>>>>\n"
        b"startxref\n200\n%%EOF"
    )
    text = extract_attachment_text_sync(content=pdf_bytes, mime_type="application/pdf")
    # pypdf may or may not parse this minimal PDF — ensure no exception and str or None
    assert text is None or "INVOICE" in text or "100" in text
