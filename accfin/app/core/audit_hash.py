"""Tamper-evident audit hash chain — `06` §13.1."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID


def _json_text(value: dict | list | None) -> str:
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def compute_tamper_hash(
    *,
    previous_hash: str | None,
    entity_type: str,
    entity_id: UUID | None,
    action: str,
    before_state: dict | None,
    after_state: dict | None,
    timestamp: datetime,
) -> str:
    """SHA-256 chain payload per `06` §13.1."""
    parts = [
        previous_hash or "",
        entity_type,
        str(entity_id) if entity_id else "",
        action,
        _json_text(before_state),
        _json_text(after_state),
        timestamp.isoformat(),
    ]
    digest = hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()
    return digest


def format_tamper_hash(digest: str) -> str:
    return f"sha256:{digest}"
