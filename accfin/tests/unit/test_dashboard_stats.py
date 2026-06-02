"""Dashboard stats unit tests — `0.15.09-dashboard-redesign`."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.dashboard_stats import (
    compute_success_rate,
    normalize_cases_by_status,
    sgt_period_bounds,
    _count_processing_started,
    DASHBOARD_STATUS_KEYS,
)


def test_dashboard_stats_cases_by_status() -> None:
    raw = {"posted": 47, "processing": 2, "unknown_status": 5}
    normalized = normalize_cases_by_status(raw)
    assert normalized["posted"] == 47
    assert normalized["processing"] == 2
    assert normalized["pending_confirmation"] == 0
    assert set(normalized.keys()) == set(DASHBOARD_STATUS_KEYS)
    assert sum(normalized.values()) == 49


def test_compute_success_rate_defaults_to_one() -> None:
    assert compute_success_rate(0, 0, 0) == 1.0


def test_compute_success_rate_ratio() -> None:
    assert compute_success_rate(87, 10, 3) == 0.87


def test_sgt_period_bounds_monday_week_start() -> None:
    # 2026-06-02 is Tuesday in SGT; week starts Monday 2026-06-01
    period = sgt_period_bounds(datetime(2026, 6, 2, 10, 0, tzinfo=UTC))
    assert period.today_start.isoformat().startswith("2026-06-02")
    assert period.week_start.isoformat().startswith("2026-06-01")


@pytest.mark.asyncio
async def test_dashboard_queue_depths() -> None:
    mock_redis = AsyncMock()
    mock_redis.llen = AsyncMock(side_effect=[2, 0])

    with patch("app.services.dashboard_stats.get_redis", return_value=mock_redis):
        from app.services.dashboard_stats import _queue_depths

        depths = await _queue_depths()

    assert depths.accounts_queue == 2
    assert depths.intake_queue == 0


@pytest.mark.asyncio
async def test_dashboard_stats_agent_performance_today() -> None:
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 2
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=mock_result)

    count = await _count_processing_started(
        mock_session,
        actor="expense-worker",
        since=sgt_period_bounds().today_start,
    )
    assert count == 2
