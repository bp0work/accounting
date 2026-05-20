"""In-app notification delivery — `18` §6 (MVP)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.notification import NotificationRepository
from app.services.event_bus import publish_user_event


class NotificationDispatcher:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = NotificationRepository(session)

    async def notify_approval_requested(
        self,
        *,
        approver_id: UUID,
        approval_id: UUID,
        case_id: UUID,
        case_number: str,
        subject: str,
    ) -> None:
        event_id = f"approval-requested-{approval_id}"
        await self._repo.create_in_app(
            user_id=approver_id,
            event_key="approval.requested",
            title="Approval requested",
            body=subject[:500],
            source_event_id=event_id,
            case_id=case_id,
            case_number=case_number,
            action_url=f"/approvals/{approval_id}",
        )
        await publish_user_event(
            str(approver_id),
            "approval.requested",
            {
                "approval_id": str(approval_id),
                "case_id": str(case_id),
                "case_number": case_number,
            },
        )

    async def notify_approval_resolved(
        self,
        *,
        user_id: UUID,
        event_key: str,
        approval_id: UUID,
        case_number: str,
        message: str,
    ) -> None:
        event_id = f"{event_key}-{approval_id}-{uuid4().hex[:8]}"
        await self._repo.create_in_app(
            user_id=user_id,
            event_key=event_key,
            title="Approval update",
            body=message[:500],
            source_event_id=event_id,
            case_number=case_number,
            action_url=f"/approvals/{approval_id}",
        )
        await publish_user_event(
            str(user_id),
            event_key,
            {"approval_id": str(approval_id), "case_number": case_number},
        )
