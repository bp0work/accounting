"""Audit log API schemas — `05` §14."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuditUserRef(BaseModel):
    id: UUID | None = None
    name: str | None = None
    ip_address: str | None = None


class AuditLogItem(BaseModel):
    id: UUID
    timestamp: datetime
    action: str
    entity_type: str
    entity_id: UUID | None = None
    case_id: UUID | None = None
    case_number: str | None = None
    user: AuditUserRef | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    metadata: dict = Field(default_factory=dict)
    correlation_id: str | None = None
    tamper_hash: str
    previous_hash: str | None = None


class AuditLogListResponse(BaseModel):
    data: list[AuditLogItem]


class AuditLogExportRequest(BaseModel):
    format: str = "csv"
    from_date: datetime | None = None
    to_date: datetime | None = None
    entity_type: str | None = None
    actions: list[str] | None = None


class AuditLogExportResponse(BaseModel):
    export_id: str
    status: str = "ready"
    download_url: str | None = None
    estimated_ready: datetime | None = None


class IntegrityCheckResponse(BaseModel):
    integrity_status: str
    total_entries_checked: int
    first_entry_date: str | None = None
    last_entry_date: str | None = None
    violations: list[dict] = Field(default_factory=list)
