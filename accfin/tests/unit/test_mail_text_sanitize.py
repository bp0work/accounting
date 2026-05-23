from app.services.mail.text_sanitize import sanitize_text


def test_sanitize_text_null_and_nbsp():
    assert sanitize_text("hello\x00world") == "helloworld"
    assert sanitize_text("a\u00a0b") == "a b"
    assert sanitize_text(None) is None


def test_sanitize_text_invalid_utf8_surrogate():
    result = sanitize_text("ok\ud800there")
    assert "\ud800" not in result
    assert result.startswith("ok") and result.endswith("there")
