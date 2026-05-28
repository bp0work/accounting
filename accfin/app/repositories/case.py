"""Case persistence — Phase 4."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import Case, CaseTimeline
from app.models.ledger import JournalEntry
from app.models.mail import Email
from app.models.user import User
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowTransition
from app.services.case_metrics import TERMINAL_STATUSES


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def generate_case_number(self) -> str:
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"CAS-{today}-"
        result = await self._session.execute(
            select(func.count()).select_from(Case).where(Case.case_number.like(f"{prefix}%"))
        )
        seq = int(result.scalar_one() or 0) + 1
        return f"{prefix}{seq:04d}"

    async def get(self, case_id: UUID) -> Case | None:
        result = await self._session.execute(
            select(Case)
            .options(selectinload(Case.timeline), selectinload(Case.workflow_instance))
            .where(Case.id == case_id)
        )
        return result.scalar_one_or_none()

    async def get_for_retry(self, case_id: UUID) -> Case | None:
        """Load case for manual retry without relationship eager loads (avoids greenlet on flush)."""
        result = await self._session.execute(select(Case).where(Case.id == case_id))
        return result.scalar_one_or_none()

    def _date_range_filter(self, q, *, date_from: date | None, date_to: date | None):
        if date_from is not None:
            start = datetime.combine(date_from, time.min, tzinfo=UTC)
            q = q.where(Case.created_at >= start)
        if date_to is not None:
            end = datetime.combine(date_to, time.min, tzinfo=UTC) + timedelta(days=1)
            q = q.where(Case.created_at < end)
        return q

    async def list_cases(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Case]:
        q = (
            select(Case)
            .options(selectinload(Case.timeline))
            .order_by(Case.created_at.desc())
            .limit(limit)
        )
        if status:
            q = q.where(Case.status == status)
        q = self._date_range_filter(q, date_from=date_from, date_to=date_to)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Case.status, func.count()).group_by(Case.status)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def average_processing_minutes_completed(self) -> float | None:
        result = await self._session.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        Case.completed_at - Case.created_at,
                    )
                )
            ).where(Case.completed_at.isnot(None))
        )
        avg_seconds = result.scalar_one_or_none()
        if avg_seconds is None:
            return None
        return round(float(avg_seconds) / 60.0, 1)

    async def list_overdue_cases(self, *, limit: int = 20) -> list[Case]:
        now = datetime.now(UTC)
        q = (
            select(Case)
            .options(selectinload(Case.timeline))
            .where(
                Case.status.notin_(tuple(TERMINAL_STATUSES)),
                Case.sla_deadline.isnot(None),
                Case.sla_deadline < now,
            )
            .order_by(Case.sla_deadline.asc())
            .limit(limit)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_cases_for_export(
        self, *, date_from: date, date_to: date
    ) -> list[tuple[Case, JournalEntry | None, str | None]]:
        """Cases in range with latest posted (or any) journal entry per case."""
        q = select(Case).order_by(Case.created_at.asc())
        q = self._date_range_filter(q, date_from=date_from, date_to=date_to)
        result = await self._session.execute(q)
        cases = list(result.scalars().all())
        rows: list[tuple[Case, JournalEntry | None, str | None]] = []
        for case in cases:
            je_result = await self._session.execute(
                select(JournalEntry, User.email)
                .outerjoin(User, User.id == JournalEntry.posted_by)
                .where(JournalEntry.case_id == case.id)
                .order_by(JournalEntry.created_at.desc())
                .limit(1)
            )
            row = je_result.first()
            if row:
                rows.append((case, row[0], row[1]))
            else:
                rows.append((case, None, None))
        return rows

    async def get_email(self, email_id: UUID) -> Email | None:
        result = await self._session.execute(select(Email).where(Email.id == email_id))
        return result.scalar_one_or_none()

    async def create_manual_case(
        self,
        *,
        case_type: str,
        subject: str,
        description: str | None = None,
        amount_value=None,
        amount_currency: str = "SGD",
        priority: str = "medium",
    ) -> Case:
        case_number = await self.generate_case_number()
        case = Case(
            case_number=case_number,
            type=case_type,
            status="inbound",
            priority=priority,
            subject=subject,
            description=description,
            amount_value=amount_value,
            amount_currency=amount_currency,
            classification_metadata={"source": "ui"},
        )
        self._session.add(case)
        await self._session.flush()
        return case

    async def create_case_from_email(
        self,
        *,
        email: Email,
        case_type: str,
        confidence: float,
    ) -> Case:
        case_number = await self.generate_case_number()
        case = Case(
            case_number=case_number,
            type=case_type,
            status="inbound",
            subject=email.subject,
            description=email.body_preview,
            email_id=email.id,
            confidence_score=confidence,
            classification_metadata={
                "source": "intake",
                "mailbox": email.mailbox_address,
                "from_address": email.from_address,
            },
        )
        self._session.add(case)
        await self._session.flush()

        email.case_id = case.id
        email.case_number = case.case_number
        email.status = "classified"
        await self._session.flush()
        return case

    async def ensure_workflow_definition(self, case_type: str) -> WorkflowDefinition:
        result = await self._session.execute(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.case_type == case_type, WorkflowDefinition.is_active.is_(True))
            .order_by(WorkflowDefinition.version.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        definition = WorkflowDefinition(
            name=f"default_{case_type}",
            version=1,
            case_type=case_type,
            description="Auto-seeded default workflow",
        )
        self._session.add(definition)
        await self._session.flush()
        return definition

    async def create_workflow_instance(self, case: Case, definition: WorkflowDefinition) -> WorkflowInstance:
        instance = WorkflowInstance(
            case_id=case.id,
            definition_id=definition.id,
            current_state=case.status,
        )
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def record_transition(
        self,
        *,
        instance: WorkflowInstance,
        from_state: str,
        to_state: str,
        trigger: str,
        actor: str,
        metadata: dict | None = None,
    ) -> WorkflowTransition:
        instance.current_state = to_state
        transition = WorkflowTransition(
            instance_id=instance.id,
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            actor=actor,
            extra_metadata=metadata or {},
        )
        self._session.add(transition)
        await self._session.flush()
        return transition

    async def add_timeline(
        self,
        *,
        case_id: UUID,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        actor: str,
        description: str | None = None,
        metadata: dict | None = None,
        actor_user_id: UUID | None = None,
    ) -> CaseTimeline:
        entry = CaseTimeline(
            id=uuid4(),
            case_id=case_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            actor_user_id=actor_user_id,
            description=description,
            extra_metadata=metadata or {},
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
