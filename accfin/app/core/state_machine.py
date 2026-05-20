"""Table-driven case state machine — `08` §12."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class CaseStatus(str, Enum):
    INBOUND = "inbound"
    CLASSIFIED = "classified"
    PROCESSING = "processing"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    POSTED = "posted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXCEPTION = "exception"
    MANUAL_REVIEW = "manual_review"
    ON_HOLD = "on_hold"


@dataclass
class Transition:
    trigger: str
    from_state: CaseStatus
    to_state: CaseStatus
    guard: Callable[..., bool] | None = None
    entry_actions: list[Callable[..., None]] = field(default_factory=list)
    exit_actions: list[Callable[..., None]] = field(default_factory=list)
    actor_permissions: list[str] = field(default_factory=list)


@dataclass
class TransitionResult:
    success: bool
    from_state: CaseStatus
    to_state: CaseStatus | None = None
    triggered_by: str | None = None
    guard_failed: str | None = None
    actions_executed: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class CaseStateMachine:
    TERMINAL_STATES = {CaseStatus.COMPLETED}

    def __init__(self) -> None:
        self._transitions: dict[tuple[CaseStatus, str], list[Transition]] = {}
        self._setup_transitions()

    def _add_transition(self, transition: Transition) -> None:
        key = (transition.from_state, transition.trigger)
        self._transitions.setdefault(key, []).append(transition)

    def _setup_transitions(self) -> None:
        self._add_transition(
            Transition(
                trigger="ai_classified",
                from_state=CaseStatus.INBOUND,
                to_state=CaseStatus.CLASSIFIED,
                guard=self._guard_classification_confidence,
            )
        )
        self._add_transition(
            Transition(
                trigger="classification_failed",
                from_state=CaseStatus.INBOUND,
                to_state=CaseStatus.MANUAL_REVIEW,
                guard=self._guard_low_confidence,
            )
        )
        self._add_transition(
            Transition(
                trigger="human_classified",
                from_state=CaseStatus.INBOUND,
                to_state=CaseStatus.CLASSIFIED,
                actor_permissions=["cases:write"],
            )
        )
        self._add_transition(
            Transition(
                trigger="processing_started",
                from_state=CaseStatus.CLASSIFIED,
                to_state=CaseStatus.PROCESSING,
            )
        )
        self._add_transition(
            Transition(
                trigger="human_escalated",
                from_state=CaseStatus.CLASSIFIED,
                to_state=CaseStatus.MANUAL_REVIEW,
                actor_permissions=["cases:write"],
            )
        )
        self._add_transition(
            Transition(
                trigger="extraction_complete",
                from_state=CaseStatus.PROCESSING,
                to_state=CaseStatus.APPROVED,
                guard=self._guard_stp_eligible,
            )
        )
        self._add_transition(
            Transition(
                trigger="extraction_complete",
                from_state=CaseStatus.PROCESSING,
                to_state=CaseStatus.PENDING_APPROVAL,
                guard=self._guard_not_stp,
            )
        )
        self._add_transition(
            Transition(
                trigger="processing_error",
                from_state=CaseStatus.PROCESSING,
                to_state=CaseStatus.EXCEPTION,
                guard=self._guard_retry_available,
            )
        )
        self._add_transition(
            Transition(
                trigger="processing_error",
                from_state=CaseStatus.PROCESSING,
                to_state=CaseStatus.MANUAL_REVIEW,
                guard=self._guard_max_retries,
            )
        )
        self._add_transition(
            Transition(
                trigger="policy_violation",
                from_state=CaseStatus.PROCESSING,
                to_state=CaseStatus.PENDING_APPROVAL,
                guard=self._guard_violation_needs_approval,
            )
        )
        self._add_transition(
            Transition(
                trigger="approved",
                from_state=CaseStatus.PENDING_APPROVAL,
                to_state=CaseStatus.APPROVED,
                guard=self._guard_is_authorized_approver,
            )
        )
        self._add_transition(
            Transition(
                trigger="rejected",
                from_state=CaseStatus.PENDING_APPROVAL,
                to_state=CaseStatus.REJECTED,
                guard=self._guard_is_authorized_approver,
            )
        )
        self._add_transition(
            Transition(
                trigger="journal_posted",
                from_state=CaseStatus.APPROVED,
                to_state=CaseStatus.POSTED,
            )
        )
        self._add_transition(
            Transition(
                trigger="completion_verified",
                from_state=CaseStatus.POSTED,
                to_state=CaseStatus.COMPLETED,
            )
        )
        self._add_transition(
            Transition(
                trigger="retry_triggered",
                from_state=CaseStatus.EXCEPTION,
                to_state=CaseStatus.PROCESSING,
                guard=self._guard_auto_recoverable,
            )
        )
        self._add_transition(
            Transition(
                trigger="retry_failed",
                from_state=CaseStatus.EXCEPTION,
                to_state=CaseStatus.MANUAL_REVIEW,
            )
        )
        self._add_transition(
            Transition(
                trigger="human_intervened",
                from_state=CaseStatus.EXCEPTION,
                to_state=CaseStatus.MANUAL_REVIEW,
                actor_permissions=["cases:write"],
            )
        )
        self._add_transition(
            Transition(
                trigger="resolved",
                from_state=CaseStatus.MANUAL_REVIEW,
                to_state=CaseStatus.PROCESSING,
                actor_permissions=["cases:write"],
            )
        )
        self._add_transition(
            Transition(
                trigger="reworked",
                from_state=CaseStatus.REJECTED,
                to_state=CaseStatus.MANUAL_REVIEW,
                actor_permissions=["cases:write"],
            )
        )
        self._add_transition(
            Transition(
                trigger="released",
                from_state=CaseStatus.ON_HOLD,
                to_state=CaseStatus.PROCESSING,
                actor_permissions=["cases:write"],
            )
        )

    def _guard_classification_confidence(self, _case: Any, context: dict, **_kw: Any) -> bool:
        return float(context.get("confidence", 0)) >= 0.70

    def _guard_low_confidence(self, _case: Any, context: dict, **_kw: Any) -> bool:
        return float(context.get("confidence", 1.0)) < 0.70

    def _guard_stp_eligible(self, case: Any, context: dict, **_kw: Any) -> bool:
        score = float(case.confidence_score or 0)
        counterparty = context.get("counterparty")
        recurring = bool(getattr(counterparty, "is_recurring", False)) if counterparty else False
        return (
            score >= 0.90
            and not (case.risk_flags or [])
            and recurring
            and bool(context.get("policy_pass", False))
        )

    def _guard_not_stp(self, case: Any, context: dict, **_kw: Any) -> bool:
        return not self._guard_stp_eligible(case, context)

    def _guard_retry_available(self, _case: Any, context: dict, **_kw: Any) -> bool:
        workflow = context.get("workflow")
        if workflow is None:
            return True
        return int(workflow.retry_count) < int(workflow.max_retries)

    def _guard_max_retries(self, case: Any, context: dict, **_kw: Any) -> bool:
        return not self._guard_retry_available(case, context)

    def _guard_violation_needs_approval(self, _case: Any, context: dict, **_kw: Any) -> bool:
        return context.get("violation_type") != "blocking"

    def _guard_is_authorized_approver(self, _case: Any, context: dict, **_kw: Any) -> bool:
        user = context.get("user")
        if user is None:
            return False
        perms = getattr(user, "permissions", []) or []
        return "approvals:approve" in perms or "approvals:admin" in perms

    def _guard_auto_recoverable(self, _case: Any, context: dict, **_kw: Any) -> bool:
        return context.get("exception_category") in {
            "ai_timeout",
            "ai_parse_error",
            "ai_unavailable",
            "db_transient",
            "external_service",
            "unknown",
        }

    def can_transition(
        self, case: Any, trigger: str, actor: Any | None = None, context: dict | None = None
    ) -> bool:
        return self.transition(case, trigger, actor, context, dry_run=True).success

    def transition(
        self,
        case: Any,
        trigger: str,
        actor: Any | None = None,
        context: dict | None = None,
        *,
        dry_run: bool = False,
    ) -> TransitionResult:
        context = context or {}
        current = CaseStatus(case.status)
        candidates = self._transitions.get((current, trigger), [])

        if not candidates:
            return TransitionResult(
                success=False,
                from_state=current,
                guard_failed=f"No transition for trigger '{trigger}' from '{current.value}'",
            )

        for candidate in candidates:
            if candidate.actor_permissions and actor is not None:
                perms = getattr(actor, "permissions", []) or []
                if not any(p in perms for p in candidate.actor_permissions):
                    continue

            if candidate.guard is not None:
                try:
                    if not candidate.guard(case, context, actor=actor):
                        continue
                except Exception as exc:
                    return TransitionResult(
                        success=False,
                        from_state=current,
                        guard_failed=f"Guard error: {exc}",
                    )

            if dry_run:
                return TransitionResult(
                    success=True,
                    from_state=current,
                    to_state=candidate.to_state,
                    triggered_by=trigger,
                )

            for action in candidate.exit_actions:
                action(case, context, actor=actor)

            case.status = candidate.to_state.value
            if hasattr(case, "updated_at"):
                case.updated_at = datetime.now(UTC)

            executed: list[str] = []
            for action in candidate.entry_actions:
                action(case, context, actor=actor)
                executed.append(action.__name__)

            return TransitionResult(
                success=True,
                from_state=current,
                to_state=candidate.to_state,
                triggered_by=trigger,
                actions_executed=executed,
            )

        return TransitionResult(
            success=False,
            from_state=current,
            guard_failed="No matching transition passed guard conditions",
        )
