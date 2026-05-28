from datetime import UTC, datetime, timedelta

from workers.common.ap_validation import extract_sender_validation


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


def test_validation_rejects_wrong_date_format() -> None:
    result = extract_sender_validation(
        subject="validated 2026-05-28",
        body="",
    )
    assert result["sender_validated"] is False
    assert result["validation_date"] is None
    assert "validated dd/mm/yyyy" in str(result["failure_reason"])


def test_validation_rejects_old_date() -> None:
    old_date = (datetime.now(UTC).date() - timedelta(days=10))
    result = extract_sender_validation(
        subject=f"Validated {old_date.strftime('%d/%m/%Y')}",
        body="",
    )
    assert result["sender_validated"] is False
    assert result["validation_date"] == old_date.isoformat()
    assert "validated dd/mm/yyyy" in str(result["failure_reason"])


def test_validation_rejects_when_keyword_without_date() -> None:
    result = extract_sender_validation(
        subject="validated document attached",
        body="please check",
    )
    assert result["sender_validated"] is False
    assert result["validation_date"] is None
    assert "validated dd/mm/yyyy" in str(result["failure_reason"])
