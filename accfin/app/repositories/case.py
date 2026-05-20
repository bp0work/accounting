"""Case persistence — Phase 4."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import Case, CaseTimeline
from app.models.mail import Email
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowTransition


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

    async def list_cases(self, *, limit: int = 50, status: str | None = None) -> list[Case]:
        q = select(Case).order_by(Case.created_at.desc()).limit(limit)
        if status:
            q = q.where(Case.status == status)
        result = await self._session.execute(q)
        return list(result.scalars().all())

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
