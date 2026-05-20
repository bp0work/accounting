"""Notification preference and inbox schemas — `05` §4.13–4.18."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationTemplateResponse(BaseModel):
    id: UUID
    event_key: str
    display_name: str
    description: str | None = None
    default_email: bool
    default_in_app: bool
    user_overridable: bool
    sort_order: int

    model_config = {"from_attributes": True}


class SubscriptionPreference(BaseModel):
    event_key: str
    email: bool = True
    in_app: bool = True
    digest: str = "off"


class NotificationPreferencesResponse(BaseModel):
    quiet_hours: dict = Field(default_factory=dict)
    channels: dict = Field(default_factory=lambda: {"email": True, "in_app": True})
    subscriptions: list[SubscriptionPreference] = Field(default_factory=list)


class NotificationPreferencesUpdate(BaseModel):
    quiet_hours: dict = Field(default_factory=dict)
    channels: dict = Field(default_factory=lambda: {"email": True, "in_app": True})
    subscriptions: list[SubscriptionPreference] = Field(default_factory=list)


class InboxNotification(BaseModel):
    id: UUID
    event_key: str
    title: str
    body: str
    is_read: bool
    case_id: UUID | None = None
    case_number: str | None = None
    action_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationsListResponse(BaseModel):
    data: list[InboxNotification]
    unread_count: int


class MarkNotificationsReadRequest(BaseModel):
    notification_ids: list[UUID] = Field(default_factory=list)
    all: bool = False
