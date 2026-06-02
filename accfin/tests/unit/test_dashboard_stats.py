"""Dashboard stats unit tests — `0.15.09-dashboard-redesign`."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.dashboard_stats import (
    AP_INTERVENTION_MAP,
    AR_INTERVENTION_MAP,
    EXPENSE_INTERVENTION_MAP,
    KPI_PERIOD_DAYS,
    compute_success_rate,
    normalize_cases_by_status,
    sgt_period_bounds,
    _aggregate_interventions,
    _count_processing_started,
    _intervention_pct,
    _parsing_awaiting_confirmation_count_for_period,
    _reason_code_counts_for_period,
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


def test_kpi_expense_reason_code_mapping() -> None:
    assert EXPENSE_INTERVENTION_MAP["unable_to_parse"] == ["EXP_PARSING_INCOMPLETE"]
    assert EXPENSE_INTERVENTION_MAP["missing_travel_requisition"] == [
        "EXP_MISSING_TRAVEL_REQUISITION"
    ]
    assert "EXP_POLICY_EXCEEDED" in EXPENSE_INTERVENTION_MAP["policy_exceeded"]


def test_kpi_ap_reason_code_mapping() -> None:
    assert AP_INTERVENTION_MAP["missing_supporting_doc"] == [
        "AP_MISSING_PO",
        "AP_MISSING_CONTRACT",
        "AP_MISSING_GRN",
        "AP_MISSING_DO",
    ]


def test_kpi_ar_reason_code_mapping() -> None:
    assert AR_INTERVENTION_MAP["credit_term_exposure"] == [
        "AR_CREDIT_LIMIT_EXCEEDED",
        "AR_OVERDUE",
    ]


def test_kpi_period_aggregation_30_60_90() -> None:
    assert KPI_PERIOD_DAYS == (("30d", 30), ("60d", 60), ("90d", 90))


def test_kpi_percentage_calculation() -> None:
    assert _intervention_pct(8, 45) == 17.8


def test_kpi_zero_total_no_division_error() -> None:
    interventions = _aggregate_interventions(
        reason_counts={"EXP_PARSING_INCOMPLETE": 3},
        total_cases=0,
        intervention_map=EXPENSE_INTERVENTION_MAP,
    )
    assert interventions["unable_to_parse"].pct == 0.0
    assert interventions["total_interventions"].pct == 0.0


@pytest.mark.asyncio
async def test_kpi_distinct_case_count_per_escalation() -> None:
    captured_sql = {}

    class _Result:
        def all(self):
            return []

    class _Session:
        async def execute(self, stmt):
            captured_sql["sql"] = str(stmt)
            return _Result()

    await _reason_code_counts_for_period(
        _Session(),  # type: ignore[arg-type]
        case_types=("expense_claim",),
        reason_codes=["EXP_DUPLICATE"],
        cutoff=datetime.now(UTC),
    )
    assert "count(distinct(case_escalations.case_id))" in captured_sql["sql"].lower()


@pytest.mark.asyncio
async def test_kpi_parsing_confirmation_count() -> None:
    captured_sql = {}

    class _Result:
        def scalar_one(self):
            return 5

    class _Session:
        async def execute(self, stmt):
            captured_sql["sql"] = str(stmt)
            return _Result()

    count = await _parsing_awaiting_confirmation_count_for_period(
        _Session(),  # type: ignore[arg-type]
        case_types=("expense_claim",),
        cutoff=datetime.now(UTC),
    )
    assert count == 5
    sql = captured_sql["sql"].lower()
    assert "case_timeline.event_type" in sql
    assert "parsing_awaiting_confirmation" in sql
    assert "count(distinct(case_timeline.case_id))" in sql
