"""Operations dashboard aggregate stats — `0.15.09-dashboard-redesign`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case as sql_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.models.case import Case, CaseTimeline
from app.models.executive_mail import CaseEscalation
from app.models.mail import Email, MailGatewayConfig
from app.schemas.auth import TokenData
from app.schemas.dashboard import (
    AgentPerformance,
    DashboardPeriod,
    DashboardQueueDepths,
    DashboardStatsResponse,
    GatewayPerformance,
    InterventionStat,
    KpiPeriod,
    WorkerPerformance,
    WorkerKpi,
)

SGT = ZoneInfo("Asia/Singapore")

DASHBOARD_STATUS_KEYS: tuple[str, ...] = (
    "pending_confirmation",
    "pending_approval",
    "on_hold",
    "manual_review",
    "posted",
    "rejected",
    "case_rejected",
    "reversed",
    "classified",
    "processing",
)

WORKER_ACTORS: dict[str, str] = {
    "accounts_worker": "accounts-worker",
    "expense_worker": "expense-worker",
    "ap_worker": "ap-worker",
    "ar_worker": "ar-worker",
}

EXPENSE_CASE_TYPES = ("expense_claim",)
AP_CASE_TYPES = ("ap_invoice", "ap_po_validation", "ap_payment_proposal")
AR_CASE_TYPES = (
    "ar_invoice",
    "ar_payment_advice",
    "ar_credit_note",
    "ar_soa_request",
)

OUTCOME_STATUSES = ("posted", "rejected", "case_rejected")

KPI_PERIOD_WINDOWS: tuple[tuple[str, int, int | None], ...] = (
    ("30d", 30, None),
    ("60d", 60, 30),
    ("90d", 90, 60),
)

EXPENSE_INTERVENTION_MAP: dict[str, list[str]] = {
    "unable_to_parse": ["EXP_PARSING_INCOMPLETE"],
    "duplicate_document": ["EXP_DUPLICATE"],
    "counterparty_not_found": ["EXP_SUBMITTER_NOT_FOUND"],
    "document_not_validated": ["EXP_SENDER_NOT_VALIDATED"],
    "exchange_rate_issue": ["EXP_CURRENCY_CONVERSION_REQUIRED"],
    "policy_exceeded": ["EXP_POLICY_EXCEEDED", "EXP_RECEIPT_INVALID"],
    "missing_travel_requisition": ["EXP_MISSING_TRAVEL_REQUISITION"],
    "out_of_period": ["PERIOD_CLOSED"],
    "coa_mapping": ["EXP_COA_NOT_FOUND"],
    "journal_entry": ["JOURNAL_ENTRY_FAILED"],
}
# NOTE (0.15.13): policy_exceeded can look inflated in UAT because historical
# policy-engine debug runs generated extra escalation rows; this is expected to
# normalize as production-only traffic dominates the KPI window.

AP_INTERVENTION_MAP: dict[str, list[str]] = {
    "unable_to_parse": ["AP_PARSING_INCOMPLETE"],
    "duplicate_document": ["AP_DUPLICATE"],
    "counterparty_not_found": ["AP_VENDOR_NOT_FOUND"],
    "document_not_validated": ["AP_SENDER_NOT_VALIDATED"],
    "exchange_rate_issue": ["AP_CURRENCY_CONVERSION_REQUIRED"],
    "missing_supporting_doc": [
        "AP_MISSING_PO",
        "AP_MISSING_CONTRACT",
        "AP_MISSING_GRN",
        "AP_MISSING_DO",
    ],
    "out_of_period": ["PERIOD_CLOSED"],
    "coa_mapping": ["AP_COA_NOT_FOUND"],
    "journal_entry": ["JOURNAL_ENTRY_FAILED"],
}

AR_INTERVENTION_MAP: dict[str, list[str]] = {
    "unable_to_parse": ["AR_PARSING_INCOMPLETE"],
    "duplicate_document": ["AR_DUPLICATE"],
    "counterparty_not_found": ["AR_CUSTOMER_NOT_FOUND"],
    "credit_term_exposure": ["AR_CREDIT_LIMIT_EXCEEDED", "AR_OVERDUE"],
    "exchange_rate_issue": ["AR_CURRENCY_CONVERSION_REQUIRED"],
    "out_of_period": ["PERIOD_CLOSED"],
    "coa_mapping": ["AR_COA_NOT_FOUND"],
    "journal_entry": ["JOURNAL_ENTRY_FAILED"],
}


def sgt_period_bounds(now: datetime | None = None) -> DashboardPeriod:
    """Today and week start at midnight SGT."""
    now = now or datetime.now(SGT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SGT)
    else:
        now = now.astimezone(SGT)
    today_start = datetime(now.year, now.month, now.day, tzinfo=SGT)
    week_start = today_start - timedelta(days=now.weekday())
    return DashboardPeriod(today_start=today_start, week_start=week_start)


def normalize_cases_by_status(raw: dict[str, int]) -> dict[str, int]:
    """Ensure all dashboard status keys exist (zero-filled)."""
    return {key: int(raw.get(key, 0)) for key in DASHBOARD_STATUS_KEYS}


def compute_success_rate(posted: int, rejected: int, case_rejected: int) -> float:
    total = posted + rejected + case_rejected
    if total == 0:
        return 1.0
    return round(posted / total, 4)


def _intervention_pct(count: int, total_cases: int) -> float:
    if total_cases <= 0:
        return 0.0
    return round((count / total_cases) * 100, 1)


def _aggregate_interventions(
    *,
    reason_counts: dict[str, int],
    total_cases: int,
    intervention_map: dict[str, list[str]],
) -> dict[str, InterventionStat]:
    interventions: dict[str, InterventionStat] = {}
    total_interventions = 0
    for key, reason_codes in intervention_map.items():
        count = sum(int(reason_counts.get(code, 0)) for code in reason_codes)
        total_interventions += count
        interventions[key] = InterventionStat(
            count=count,
            pct=_intervention_pct(count, total_cases),
        )
    interventions["total_interventions"] = InterventionStat(
        count=total_interventions,
        pct=_intervention_pct(total_interventions, total_cases),
    )
    return interventions


async def _count_emails_since(session: AsyncSession, since: datetime) -> int:
    since_utc = since.astimezone(UTC)
    result = await session.execute(
        select(func.count()).select_from(Email).where(Email.created_at >= since_utc)
    )
    return int(result.scalar_one() or 0)


async def _gateway_avg_processing_seconds(session: AsyncSession, since: datetime) -> float:
    since_utc = since.astimezone(UTC)
    end_col = func.coalesce(Email.processed_at, Email.classified_at, Email.created_at)
    result = await session.execute(
        select(func.avg(func.extract("epoch", end_col - Email.received_at))).where(
            Email.created_at >= since_utc,
            Email.received_at.isnot(None),
        )
    )
    avg = result.scalar_one_or_none()
    return round(float(avg or 0.0), 1)


async def _gateway_last_poll(session: AsyncSession) -> datetime | None:
    result = await session.execute(
        select(func.max(MailGatewayConfig.last_poll_at)).where(
            MailGatewayConfig.is_active.is_(True)
        )
    )
    return result.scalar_one_or_none()


async def _count_processing_started(
    session: AsyncSession,
    *,
    actor: str,
    since: datetime,
) -> int:
    since_utc = since.astimezone(UTC)
    result = await session.execute(
        select(func.count(func.distinct(CaseTimeline.case_id))).where(
            CaseTimeline.event_type == "processing_started",
            CaseTimeline.actor == actor,
            CaseTimeline.created_at >= since_utc,
        )
    )
    return int(result.scalar_one() or 0)


async def _worker_last_activity(session: AsyncSession, actor: str) -> datetime | None:
    result = await session.execute(
        select(func.max(CaseTimeline.created_at)).where(CaseTimeline.actor == actor)
    )
    return result.scalar_one_or_none()


async def _worker_avg_processing_seconds(
    session: AsyncSession,
    *,
    actor: str,
    since: datetime,
) -> float:
    since_utc = since.astimezone(UTC)
    started = (
        select(
            CaseTimeline.case_id.label("case_id"),
            func.min(CaseTimeline.created_at).label("started_at"),
        )
        .where(
            CaseTimeline.event_type == "processing_started",
            CaseTimeline.actor == actor,
            CaseTimeline.created_at >= since_utc,
        )
        .group_by(CaseTimeline.case_id)
        .subquery()
    )
    completed = (
        select(
            CaseTimeline.case_id.label("case_id"),
            func.min(CaseTimeline.created_at).label("completed_at"),
        )
        .where(CaseTimeline.to_status.in_(OUTCOME_STATUSES))
        .group_by(CaseTimeline.case_id)
        .subquery()
    )
    result = await session.execute(
        select(
            func.avg(
                func.extract("epoch", completed.c.completed_at - started.c.started_at)
            )
        ).select_from(
            started.join(completed, started.c.case_id == completed.c.case_id)
        )
    )
    avg = result.scalar_one_or_none()
    return round(float(avg or 0.0), 1)


async def _worker_outcome_counts(
    session: AsyncSession,
    *,
    actor: str,
    since: datetime,
) -> tuple[int, int, int]:
    since_utc = since.astimezone(UTC)
    started_cases = (
        select(CaseTimeline.case_id)
        .where(
            CaseTimeline.event_type == "processing_started",
            CaseTimeline.actor == actor,
            CaseTimeline.created_at >= since_utc,
        )
        .distinct()
        .subquery()
    )
    result = await session.execute(
        select(
            func.sum(sql_case((Case.status == "posted", 1), else_=0)),
            func.sum(sql_case((Case.status == "rejected", 1), else_=0)),
            func.sum(sql_case((Case.status == "case_rejected", 1), else_=0)),
        ).select_from(Case).where(Case.id.in_(select(started_cases.c.case_id)))
    )
    row = result.one()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


async def _count_cases_by_type_status(
    session: AsyncSession,
    *,
    case_types: tuple[str, ...],
    status: str,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(Case.type.in_(case_types), Case.status == status)
    )
    return int(result.scalar_one() or 0)


async def _action_required_count(session: AsyncSession, user: TokenData) -> int:
    role = (user.role or "").lower()
    if role in {"accounts_manager", "accounts_clerk"}:
        result = await session.execute(
            select(func.count())
            .select_from(Case)
            .where(
                Case.status.in_(
                    (
                        "pending_confirmation",
                        "on_hold",
                        "manual_review",
                        "pending_reversal_approval",
                    )
                )
            )
        )
        return int(result.scalar_one() or 0)
    if role in {"cfo", "finance_director"}:
        result = await session.execute(
            select(func.count())
            .select_from(Case)
            .where(
                (Case.status == "pending_reversal_approval")
                | (
                    (Case.status == "pending_approval")
                    & (Case.current_approval_tier == 3)
                )
            )
        )
        return int(result.scalar_one() or 0)
    return 0


async def _queue_depths() -> DashboardQueueDepths:
    settings = get_settings()
    redis = get_redis()
    return DashboardQueueDepths(
        accounts_queue=int(await redis.llen(settings.accounts_queue_name)),
        intake_queue=int(await redis.llen(settings.intake_queue_name)),
    )


async def _count_cases_for_period(
    session: AsyncSession,
    *,
    case_types: tuple[str, ...],
    lower_cutoff: datetime,
    upper_cutoff: datetime | None = None,
) -> int:
    filters = [
        Case.type.in_(case_types),
        Case.created_at >= lower_cutoff,
    ]
    if upper_cutoff is not None:
        filters.append(Case.created_at < upper_cutoff)
    result = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(*filters)
    )
    return int(result.scalar_one() or 0)


async def _reason_code_counts_for_period(
    session: AsyncSession,
    *,
    case_types: tuple[str, ...],
    reason_codes: list[str],
    lower_cutoff: datetime,
    upper_cutoff: datetime | None = None,
) -> dict[str, int]:
    if not reason_codes:
        return {}
    filters = [
        Case.type.in_(case_types),
        CaseEscalation.created_at >= lower_cutoff,
        CaseEscalation.reason_code.in_(reason_codes),
    ]
    if upper_cutoff is not None:
        filters.append(CaseEscalation.created_at < upper_cutoff)
    result = await session.execute(
        select(
            CaseEscalation.reason_code,
            func.count(func.distinct(CaseEscalation.case_id)),
        )
        .select_from(CaseEscalation)
        .join(Case, Case.id == CaseEscalation.case_id)
        .where(*filters)
        .group_by(CaseEscalation.reason_code)
    )
    return {str(row[0]): int(row[1]) for row in result.all() if row[0]}


async def _parsing_awaiting_confirmation_count_for_period(
    session: AsyncSession,
    *,
    case_types: tuple[str, ...],
    lower_cutoff: datetime,
    upper_cutoff: datetime | None = None,
) -> int:
    filters = [
        Case.type.in_(case_types),
        CaseTimeline.event_type == "parsing_awaiting_confirmation",
        CaseTimeline.created_at >= lower_cutoff,
    ]
    if upper_cutoff is not None:
        filters.append(CaseTimeline.created_at < upper_cutoff)
    result = await session.execute(
        select(func.count(func.distinct(CaseTimeline.case_id)))
        .select_from(CaseTimeline)
        .join(Case, Case.id == CaseTimeline.case_id)
        .where(*filters)
    )
    return int(result.scalar_one() or 0)


async def _distinct_total_interventions_for_period(
    session: AsyncSession,
    *,
    case_types: tuple[str, ...],
    reason_codes: list[str],
    lower_cutoff: datetime,
    upper_cutoff: datetime | None = None,
    include_parsing_awaiting: bool = False,
) -> int:
    filters = [
        Case.type.in_(case_types),
        CaseEscalation.created_at >= lower_cutoff,
        CaseEscalation.reason_code.in_(reason_codes),
    ]
    if upper_cutoff is not None:
        filters.append(CaseEscalation.created_at < upper_cutoff)
    escalation_result = await session.execute(
        select(func.distinct(CaseEscalation.case_id))
        .select_from(CaseEscalation)
        .join(Case, Case.id == CaseEscalation.case_id)
        .where(*filters)
    )
    case_ids = set(escalation_result.scalars().all())

    if include_parsing_awaiting:
        parsing_filters = [
            Case.type.in_(case_types),
            CaseTimeline.event_type == "parsing_awaiting_confirmation",
            CaseTimeline.created_at >= lower_cutoff,
        ]
        if upper_cutoff is not None:
            parsing_filters.append(CaseTimeline.created_at < upper_cutoff)
        parsing_result = await session.execute(
            select(func.distinct(CaseTimeline.case_id))
            .select_from(CaseTimeline)
            .join(Case, Case.id == CaseTimeline.case_id)
            .where(*parsing_filters)
        )
        case_ids.update(parsing_result.scalars().all())

    return len(case_ids)


async def _worker_kpi(
    session: AsyncSession,
    *,
    case_types: tuple[str, ...],
    intervention_map: dict[str, list[str]],
    use_parsing_awaiting_for_unable_to_parse: bool = False,
) -> WorkerKpi:
    now = datetime.now(UTC)
    all_reason_codes = [code for codes in intervention_map.values() for code in codes]
    periods: dict[str, KpiPeriod] = {}
    for label, lower_days, upper_days in KPI_PERIOD_WINDOWS:
        lower_cutoff = now - timedelta(days=lower_days)
        upper_cutoff = now - timedelta(days=upper_days) if upper_days is not None else None
        total_cases = await _count_cases_for_period(
            session,
            case_types=case_types,
            lower_cutoff=lower_cutoff,
            upper_cutoff=upper_cutoff,
        )
        reason_counts = await _reason_code_counts_for_period(
            session,
            case_types=case_types,
            reason_codes=all_reason_codes,
            lower_cutoff=lower_cutoff,
            upper_cutoff=upper_cutoff,
        )
        if use_parsing_awaiting_for_unable_to_parse:
            reason_counts["EXP_PARSING_INCOMPLETE"] = (
                await _parsing_awaiting_confirmation_count_for_period(
                    session,
                    case_types=case_types,
                    lower_cutoff=lower_cutoff,
                    upper_cutoff=upper_cutoff,
                )
            )
        interventions = _aggregate_interventions(
            reason_counts=reason_counts,
            total_cases=total_cases,
            intervention_map=intervention_map,
        )
        total_interventions = await _distinct_total_interventions_for_period(
            session,
            case_types=case_types,
            reason_codes=all_reason_codes,
            lower_cutoff=lower_cutoff,
            upper_cutoff=upper_cutoff,
            include_parsing_awaiting=use_parsing_awaiting_for_unable_to_parse,
        )
        interventions["total_interventions"] = InterventionStat(
            count=total_interventions,
            pct=_intervention_pct(total_interventions, total_cases),
        )
        periods[label] = KpiPeriod(
            total_cases=total_cases,
            interventions=interventions,
        )
    return WorkerKpi.model_validate(periods)


async def _build_worker_performance(
    session: AsyncSession,
    *,
    key: str,
    actor: str,
    period: DashboardPeriod,
    queue_depth: int,
) -> WorkerPerformance:
    posted, rejected, case_rejected = await _worker_outcome_counts(
        session, actor=actor, since=period.week_start
    )
    worker = WorkerPerformance(
        cases_today=await _count_processing_started(
            session, actor=actor, since=period.today_start
        ),
        cases_this_week=await _count_processing_started(
            session, actor=actor, since=period.week_start
        ),
        avg_processing_seconds=await _worker_avg_processing_seconds(
            session, actor=actor, since=period.week_start
        ),
        success_rate=compute_success_rate(posted, rejected, case_rejected),
        queue_depth=queue_depth,
        last_activity_at=await _worker_last_activity(session, actor),
    )
    if key == "expense_worker":
        worker.pending_confirmation = await _count_cases_by_type_status(
            session, case_types=EXPENSE_CASE_TYPES, status="pending_confirmation"
        )
        worker.pending_approval = await _count_cases_by_type_status(
            session, case_types=EXPENSE_CASE_TYPES, status="pending_approval"
        )
        worker.kpi = await _worker_kpi(
            session,
            case_types=EXPENSE_CASE_TYPES,
            intervention_map=EXPENSE_INTERVENTION_MAP,
            use_parsing_awaiting_for_unable_to_parse=True,
        )
    elif key == "ap_worker":
        worker.kpi = await _worker_kpi(
            session,
            case_types=AP_CASE_TYPES,
            intervention_map=AP_INTERVENTION_MAP,
        )
    elif key == "ar_worker":
        worker.kpi = await _worker_kpi(
            session,
            case_types=AR_CASE_TYPES,
            intervention_map=AR_INTERVENTION_MAP,
        )
    return worker


async def build_dashboard_stats(
    session: AsyncSession, *, user: TokenData
) -> DashboardStatsResponse:
    period = sgt_period_bounds()
    queues = await _queue_depths()

    gateway = GatewayPerformance(
        emails_today=await _count_emails_since(session, period.today_start),
        emails_this_week=await _count_emails_since(session, period.week_start),
        avg_processing_seconds=await _gateway_avg_processing_seconds(
            session, period.week_start
        ),
        last_poll_at=await _gateway_last_poll(session),
    )

    agent_performance = AgentPerformance(
        gateway=gateway,
        accounts_worker=await _build_worker_performance(
            session,
            key="accounts_worker",
            actor=WORKER_ACTORS["accounts_worker"],
            period=period,
            queue_depth=queues.accounts_queue,
        ),
        expense_worker=await _build_worker_performance(
            session,
            key="expense_worker",
            actor=WORKER_ACTORS["expense_worker"],
            period=period,
            queue_depth=0,
        ),
        ap_worker=await _build_worker_performance(
            session,
            key="ap_worker",
            actor=WORKER_ACTORS["ap_worker"],
            period=period,
            queue_depth=0,
        ),
        ar_worker=await _build_worker_performance(
            session,
            key="ar_worker",
            actor=WORKER_ACTORS["ar_worker"],
            period=period,
            queue_depth=0,
        ),
    )

    raw_status = await session.execute(
        select(Case.status, func.count()).group_by(Case.status)
    )
    cases_by_status = normalize_cases_by_status(
        {row[0]: int(row[1]) for row in raw_status.all()}
    )

    return DashboardStatsResponse(
        agent_performance=agent_performance,
        cases_by_status=cases_by_status,
        queue_depths=queues,
        period=period,
        action_required_count=await _action_required_count(session, user),
    )
