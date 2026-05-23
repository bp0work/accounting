"""Sanitize mail text for PostgreSQL UTF-8 columns."""


def sanitize_text(text: str | None) -> str | None:
    """Remove NUL bytes and normalize chars PostgreSQL rejects in text columns."""
    if text is None:
        return None
    cleaned = text.replace("\x00", "").replace("\xa0", " ")
    return cleaned.encode("utf-8", errors="replace").decode("utf-8")
