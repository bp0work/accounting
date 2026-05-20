"""Notification preferences and inbox — `05` §4.13–4.18."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user
from app.repositories.notification import NotificationRepository
from app.schemas.notification_api import (
    InboxNotification,
    MarkNotificationsReadRequest,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationTemplateResponse,
    NotificationsListResponse,
    SubscriptionPreference,
)
from app.schemas.auth import TokenData

router = APIRouter(tags=["Notifications"])


@router.get("/notification-templates", response_model=list[NotificationTemplateResponse])
async def list_notification_templates(
    _user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[NotificationTemplateResponse]:
    repo = NotificationRepository(session)
    templates = await repo.list_templates()
    return [NotificationTemplateResponse.model_validate(t) for t in templates]


@router.get("/users/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_my_notification_preferences(
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationPreferencesResponse:
    repo = NotificationRepository(session)
    prefs = await repo.get_preferences(user.user_id)
    if prefs is None:
        return NotificationPreferencesResponse()
    return NotificationPreferencesResponse(
        quiet_hours=prefs.quiet_hours,
        channels=prefs.channels,
        subscriptions=[
            SubscriptionPreference(**s) if isinstance(s, dict) else SubscriptionPreference.model_validate(s)
            for s in prefs.subscriptions
        ],
    )


@router.put("/users/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_my_notification_preferences(
    body: NotificationPreferencesUpdate,
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationPreferencesResponse:
    repo = NotificationRepository(session)
    prefs = await repo.upsert_preferences(
        user.user_id,
        quiet_hours=body.quiet_hours,
        channels=body.channels,
        subscriptions=[s.model_dump() for s in body.subscriptions],
    )
    await session.commit()
    return NotificationPreferencesResponse(
        quiet_hours=prefs.quiet_hours,
        channels=prefs.channels,
        subscriptions=[
            SubscriptionPreference(**s) if isinstance(s, dict) else SubscriptionPreference.model_validate(s)
            for s in prefs.subscriptions
        ],
    )


@router.get("/notifications", response_model=NotificationsListResponse)
async def list_notifications(
    is_read: bool | None = Query(default=None),
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationsListResponse:
    repo = NotificationRepository(session)
    rows, unread = await repo.list_inbox(
        user.user_id, unread_only=is_read is False, limit=50
    )
    if is_read is True:
        rows = [r for r in rows if r.is_read]
    return NotificationsListResponse(
        data=[InboxNotification.model_validate(r) for r in rows],
        unread_count=unread,
    )


@router.post("/notifications/read")
async def mark_notifications_read(
    body: MarkNotificationsReadRequest,
    user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not body.all and not body.notification_ids:
        from app.core.exceptions import AppHTTPException

        raise AppHTTPException(400, "INVALID_REQUEST", "Provide notification_ids or all=true")
    repo = NotificationRepository(session)
    count = await repo.mark_read(
        user.user_id,
        notification_ids=body.notification_ids if not body.all else None,
        mark_all=body.all,
    )
    await session.commit()
    return {"marked_read": count}
