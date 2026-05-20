"""Audit logs API — `05` §14."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.core.exceptions import AppHTTPException
from app.schemas.audit import (
    AuditLogExportRequest,
    AuditLogItem,
    AuditLogListResponse,
    IntegrityCheckResponse,
)
from app.schemas.auth import TokenData
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _to_item(entry) -> AuditLogItem:
    serialized = AuditService._serialize_row(entry)
    return AuditLogItem(**serialized)


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    entity_type: str | None = Query(None),
    entity_id: UUID | None = Query(None),
    action: str | None = Query(None),
    user_id: UUID | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    _user: TokenData = Depends(require_permission("audit-logs:read")),
    session: AsyncSession = Depends(get_db_session),
) -> AuditLogListResponse:
    service = AuditService(session)
    rows = await service.list_entries(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    return AuditLogListResponse(data=[_to_item(r) for r in rows])


@router.get("/integrity-check", response_model=IntegrityCheckResponse)
async def integrity_check(
    _user: TokenData = Depends(require_permission("audit-logs:read")),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrityCheckResponse:
    service = AuditService(session)
    result = await service.verify_integrity()
    return IntegrityCheckResponse(**result)


@router.get("/{entry_id}", response_model=AuditLogItem)
async def get_audit_log(
    entry_id: UUID,
    _user: TokenData = Depends(require_permission("audit-logs:read")),
    session: AsyncSession = Depends(get_db_session),
) -> AuditLogItem:
    service = AuditService(session)
    entry = await service.get_entry(entry_id)
    if entry is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Audit log entry not found")
    return _to_item(entry)


@router.post("/export")
async def export_audit_logs(
    body: AuditLogExportRequest,
    _user: TokenData = Depends(require_permission("audit-logs:read")),
    session: AsyncSession = Depends(get_db_session),
):
    if body.format not in {"csv", "json"}:
        raise AppHTTPException(
            status.HTTP_400_BAD_REQUEST,
            "UNSUPPORTED_FORMAT",
            "Only csv and json export are supported in this release",
        )
    service = AuditService(session)
    export_id, content, media_type = await service.export_rows(
        from_date=body.from_date,
        to_date=body.to_date,
        entity_type=body.entity_type,
        actions=body.actions,
        fmt=body.format,
    )
    extension = "csv" if body.format == "csv" else "json"
    filename = f"audit_export_{export_id}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Id": export_id,
            "X-Export-Status": "ready",
        },
        status_code=status.HTTP_200_OK,
    )
