"""Mail API schemas — `21_openapi.yaml`."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EmailAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_size: int
    mime_type: str
    content_hash: str


class EmailMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: str
    mailbox_address: str
    from_address: str
    from_name: str | None
    subject: str
    status: str
    is_duplicate: bool
    duplicate_of_id: UUID | None
    attachment_count: int
    received_at: datetime
    body_preview: str | None = None
    attachments: list[EmailAttachmentResponse] = []


class MailGatewayStatusResponse(BaseModel):
    poll_enabled: bool
    executive_mailboxes_active: int
    manager_mailboxes_configured: int
    emails_by_status: dict[str, int]
    intake_queue_depth: int


class PaginationMeta(BaseModel):
    has_more: bool = False
    next_cursor: str | None = None


class EmailListResponse(BaseModel):
    data: list[EmailMessageResponse]
    pagination: PaginationMeta
