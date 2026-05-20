"""HMAC-signed mail action tokens — `05` §8.8a."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import get_settings


def _secret() -> bytes:
    settings = get_settings()
    raw = settings.mail_action_secret or settings.hash_secret
    return raw.encode()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def hash_token(wire_token: str) -> str:
    return hashlib.sha256(wire_token.encode()).hexdigest()


def issue_escalation_token(
    *,
    escalation_id: uuid.UUID,
    case_id: uuid.UUID,
    ttl_days: int = 7,
) -> tuple[str, str, datetime]:
    """Return (wire_token, response_token_hash, token_expires_at)."""
    now = datetime.now(UTC)
    exp = now + timedelta(days=ttl_days)
    payload: dict[str, Any] = {
        "typ": "case_escalation",
        "escalation_id": str(escalation_id),
        "case_id": str(case_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload_b64 = _b64url_encode(payload_bytes)
    sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
    wire = f"{payload_b64}.{_b64url_encode(sig)}"
    return wire, hash_token(wire), exp


def verify_escalation_token(
    wire_token: str,
    *,
    escalation_id: uuid.UUID,
) -> dict[str, Any]:
    parts = wire_token.split(".", 1)
    if len(parts) != 2:
        raise ValueError("INVALID_ESCALATION_TOKEN")
    payload_b64, sig_b64 = parts
    expected_sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_sig), sig_b64):
        raise ValueError("INVALID_ESCALATION_TOKEN")
    payload = json.loads(_b64url_decode(payload_b64))
    if payload.get("typ") != "case_escalation":
        raise ValueError("INVALID_ESCALATION_TOKEN")
    if str(payload.get("escalation_id")) != str(escalation_id):
        raise ValueError("TOKEN_ESCALATION_MISMATCH")
    exp = int(payload.get("exp", 0))
    if datetime.now(UTC).timestamp() > exp:
        raise ValueError("INVALID_ESCALATION_TOKEN")
    return payload


def random_token_hash_placeholder() -> str:
    """Hash of a throwaway token for test fixtures."""
    wire = secrets.token_urlsafe(32)
    return hash_token(wire)
