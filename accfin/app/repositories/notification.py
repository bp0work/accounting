"""Notification catalog, preferences, inbox — `05` §4.13–4.18."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationTemplate, UserNotificationPreferences


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_templates(self) -> list[NotificationTemplate]:
        result = await self._session.execute(
            select(NotificationTemplate).order_by(NotificationTemplate.sort_order)
        )
        return list(result.scalars().all())

    async def get_preferences(self, user_id: UUID) -> UserNotificationPreferences | None:
        result = await self._session.execute(
            select(UserNotificationPreferences).where(
                UserNotificationPreferences.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_preferences(
        self, user_id: UUID, *, quiet_hours: dict, channels: dict, subscriptions: list
    ) -> UserNotificationPreferences:
        prefs = await self.get_preferences(user_id)
        if prefs is None:
            prefs = UserNotificationPreferences(
                user_id=user_id,
                quiet_hours=quiet_hours,
                channels=channels,
                subscriptions=subscriptions,
            )
            self._session.add(prefs)
        else:
            prefs.quiet_hours = quiet_hours
            prefs.channels = channels
            prefs.subscriptions = subscriptions
        await self._session.flush()
        return prefs

    async def create_in_app(
        self,
        *,
        user_id: UUID,
        event_key: str,
        title: str,
        body: str,
        source_event_id: str,
        case_id: UUID | None = None,
        case_number: str | None = None,
        action_url: str | None = None,
    ) -> Notification | None:
        existing = await self._session.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.source_event_id == source_event_id,
            )
        )
        if existing.scalar_one_or_none():
            return None
        row = Notification(
            user_id=user_id,
            event_key=event_key,
            title=title[:255],
            body=body[:500],
            source_event_id=source_event_id,
            case_id=case_id,
            case_number=case_number,
            action_url=action_url,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_inbox(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> tuple[list[Notification], int]:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.is_read.is_(False))
        q = q.order_by(Notification.created_at.desc()).limit(limit)
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        unread = await self._session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        return rows, int(unread or 0)

    async def mark_read(
        self, user_id: UUID, *, notification_ids: list[UUID] | None = None, mark_all: bool = False
    ) -> int:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True, read_at=datetime.now(UTC))
        )
        if not mark_all and notification_ids:
            stmt = stmt.where(Notification.id.in_(notification_ids))
        elif not mark_all:
            return 0
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)
