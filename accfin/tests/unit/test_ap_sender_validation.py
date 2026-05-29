from datetime import UTC, datetime, timedelta

from workers.common.ap_validation import extract_sender_validation, resolve_ap_sgd_amount


def test_validation_accepts_validated_dd_mm_yyyy_recent_date() -> None:
    today = datetime.now(UTC).date()
    today_ddmmyyyy = today.strftime("%d/%m/%Y")
    result = extract_sender_validation(
        subject=f"Please process - validated {today_ddmmyyyy}",
        body="Thanks",
    )
    assert result["sender_validated"] is True
    assert result["validation_date"] == today.isoformat()
    assert result["failure_reason"] is None


def test_validation_accepts_old_validated_date() -> None:
    old_date = datetime.now(UTC).date() - timedelta(days=120)
    result = extract_sender_validation(
        subject=f"Validated {old_date.strftime('%d/%m/%Y')}",
        body="",
    )
    assert result["sender_validated"] is True
    assert result["validation_date"] == old_date.isoformat()
    assert result["failure_reason"] is None


def test_validation_rejects_wrong_date_format() -> None:
    result = extract_sender_validation(
        subject="validated 2026-05-28",
        body="",
    )
    assert result["sender_validated"] is False
    assert result["validation_date"] is None
    assert "validated dd/mm/yyyy" in str(result["failure_reason"])


def test_validation_rejects_when_keyword_without_date() -> None:
    result = extract_sender_validation(
        subject="validated document attached",
        body="please check",
    )
    assert result["sender_validated"] is False
    assert result["validation_date"] is None
    assert "validated dd/mm/yyyy" in str(result["failure_reason"])


def test_resolve_ap_sgd_amount_sgd_passthrough() -> None:
    amount, fields, escalate = resolve_ap_sgd_amount(
        {"currency": "SGD", "total_amount": "100.00"}
    )
    assert escalate is False
    assert amount == 100
    assert fields["sgd_amount"] == "100.00"


def test_resolve_ap_sgd_amount_foreign_with_rate() -> None:
    amount, fields, escalate = resolve_ap_sgd_amount(
        {"currency": "USD", "total_amount": "100", "exchange_rate": "1.35"}
    )
    assert escalate is False
    assert amount == 135
    assert fields["foreign_currency"] == "USD"
    assert fields["sgd_amount"] == "135.00"


def test_resolve_ap_sgd_amount_foreign_without_rate_needs_escalation() -> None:
    amount, _fields, escalate = resolve_ap_sgd_amount(
        {"currency": "USD", "total_amount": "100"}
    )
    assert escalate is True
    assert amount == 0
