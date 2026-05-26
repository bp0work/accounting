"""Tenant email signature append — `0.14.6`."""

from app.services.mail_template_renderer import (
    TenantEmailSignature,
    append_tenant_signature,
    render_acknowledgement,
)


def test_append_signature_plain_only():
    plain, html = append_tenant_signature(
        "Hello",
        "<p>Hello</p>",
        signature=TenantEmailSignature(html="", plain="Regards,\nMMLOGISTIX"),
    )
    assert plain.endswith("MMLOGISTIX")
    assert plain.startswith("Hello")
    assert "--" in plain
    assert html == "<p>Hello</p>"


def test_append_signature_html_and_plain():
    sig = TenantEmailSignature(
        html="<p>Regards,<br/>MMLOGISTIX</p>",
        plain="Regards,\nMMLOGISTIX",
    )
    plain, html = append_tenant_signature("Body", "<p>Body</p>", signature=sig)
    assert "Regards" in plain
    assert "border-top:1px solid #e2e8f0" in html
    assert "MMLOGISTIX</p>" in html


def test_append_signature_empty_skips_separator():
    plain, html = append_tenant_signature(
        "Body",
        "<p>Body</p>",
        signature=TenantEmailSignature(),
    )
    assert plain == "Body"
    assert html == "<p>Body</p>"


def test_render_acknowledgement_includes_signature():
    plain, html = render_acknowledgement(
        {
            "case_number": "CAS-1",
            "sender_name": None,
            "original_subject": "Invoice",
            "attachment_filenames": [],
            "received_at_display": "",
            "original_body_plain": "",
        },
        signature=TenantEmailSignature(plain="Footer line"),
    )
    assert "CAS-1" in plain
    assert "Footer line" in plain
