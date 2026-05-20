from app.services.mail.parser import parse_rfc822

SAMPLE = b"""From: vendor@acme.sg
To: accar.mmlogistix@bp0.work
Subject: [CAS-2026-0001542] Invoice INV-99
Message-ID: <test-message-id@acme.sg>
Date: Mon, 19 May 2026 10:00:00 +0800
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Please find invoice attached for SGD 1,000.
"""


def test_parse_rfc822_extracts_fields():
    parsed = parse_rfc822(SAMPLE, mailbox_address="accar.mmlogistix@bp0.work")
    assert parsed.message_id == "<test-message-id@acme.sg>"
    assert parsed.from_address == "vendor@acme.sg"
    assert "CAS-2026-0001542" in (parsed.parsed_transaction_number or "")
    assert parsed.content_hash
    assert "invoice" in (parsed.body_text or "").lower()
