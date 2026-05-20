"""Normalize email bodies for deduplication — `02` §7."""

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")


def normalize_body(body: str | None) -> str:
    if not body:
        return ""
    text = body.strip().lower()
    return _WHITESPACE.sub(" ", text)


def content_hash(body: str | None) -> str:
    normalized = normalize_body(body)
    return hashlib.sha256(normalized.encode()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
