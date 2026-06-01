"""Case attachment API schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class CaseAttachmentItem(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    source: str = Field(description="email | case_upload")
    download_url: str | None = None
    expires_in_seconds: int | None = None


class CaseAttachmentListResponse(BaseModel):
    data: list[CaseAttachmentItem]
