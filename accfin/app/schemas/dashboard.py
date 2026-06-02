"""Dashboard stats API schemas — `0.15.09-dashboard-redesign`."""

from datetime import datetime

from pydantic import BaseModel, Field


class GatewayPerformance(BaseModel):
    emails_today: int = 0
    emails_this_week: int = 0
    avg_processing_seconds: float = 0.0
    last_poll_at: datetime | None = None


class WorkerPerformance(BaseModel):
    cases_today: int = 0
    cases_this_week: int = 0
    avg_processing_seconds: float = 0.0
    success_rate: float = 1.0
    queue_depth: int = 0
    last_activity_at: datetime | None = None
    pending_confirmation: int | None = None
    pending_approval: int | None = None


class AgentPerformance(BaseModel):
    gateway: GatewayPerformance
    accounts_worker: WorkerPerformance
    expense_worker: WorkerPerformance
    ap_worker: WorkerPerformance
    ar_worker: WorkerPerformance


class DashboardQueueDepths(BaseModel):
    accounts_queue: int = 0
    intake_queue: int = 0


class DashboardPeriod(BaseModel):
    today_start: datetime
    week_start: datetime


class DashboardStatsResponse(BaseModel):
    agent_performance: AgentPerformance
    cases_by_status: dict[str, int]
    queue_depths: DashboardQueueDepths
    period: DashboardPeriod
    action_required_count: int = 0
