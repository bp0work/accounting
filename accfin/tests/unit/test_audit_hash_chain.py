"""Unit tests for tamper-evident audit hash chain — `06` §13.1."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.audit_hash import compute_tamper_hash, format_tamper_hash


def test_compute_tamper_hash_first_entry():
    ts = datetime(2026, 5, 10, 16, 0, 0, tzinfo=UTC)
    entity_id = uuid4()
    digest = compute_tamper_hash(
        previous_hash=None,
        entity_type="approval",
        entity_id=entity_id,
        action="approve",
        before_state={"status": "pending"},
        after_state={"status": "approved"},
        timestamp=ts,
    )
    assert len(digest) == 64
    assert format_tamper_hash(digest).startswith("sha256:")


def test_chain_links_to_previous_hash():
    ts1 = datetime(2026, 5, 10, 16, 0, 0, tzinfo=UTC)
    ts2 = datetime(2026, 5, 10, 16, 1, 0, tzinfo=UTC)
    first = compute_tamper_hash(
        previous_hash=None,
        entity_type="user",
        entity_id=uuid4(),
        action="login",
        before_state=None,
        after_state={"ok": True},
        timestamp=ts1,
    )
    second = compute_tamper_hash(
        previous_hash=first,
        entity_type="user",
        entity_id=uuid4(),
        action="logout",
        before_state=None,
        after_state=None,
        timestamp=ts2,
    )
    assert first != second


def test_tamper_detected_when_payload_changes():
    ts = datetime(2026, 5, 10, 16, 0, 0, tzinfo=UTC)
    entity_id = uuid4()
    original = compute_tamper_hash(
        previous_hash=None,
        entity_type="approval",
        entity_id=entity_id,
        action="approve",
        before_state={"status": "pending"},
        after_state={"status": "approved"},
        timestamp=ts,
    )
    tampered = compute_tamper_hash(
        previous_hash=None,
        entity_type="approval",
        entity_id=entity_id,
        action="approve",
        before_state={"status": "pending"},
        after_state={"status": "rejected"},
        timestamp=ts,
    )
    assert original != tampered
