"""Tamper-evident audit logging — `05` §14, `06` §13.1."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_hash import compute_tamper_hash, format_tamper_hash
from app.core.metrics import AUDIT_ENTRIES
from app.models.audit import AuditLog
from app.repositories.audit import AuditRepository
from app.repositories.system_settings import SystemSettingsRepository


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuditRepository(session)
        self._settings = SystemSettingsRepository(session)

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        case_id: UUID | None = None,
        case_number: str | None = None,
        user_id: UUID | None = None,
        user_name: str | None = None,
        user_ip: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
        correlation_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> AuditLog:
        ts = timestamp or datetime.now(UTC)
        previous_hash = await self._repo.get_last_hash()
        digest = compute_tamper_hash(
            previous_hash=previous_hash,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_state=before_state,
            after_state=after_state,
            timestamp=ts,
        )
        entry = AuditLog(
            timestamp=ts,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            case_id=case_id,
            case_number=case_number,
            user_id=user_id,
            user_name=user_name,
            user_ip_address=user_ip,
            before_state=before_state,
            after_state=after_state,
            metadata_=metadata or {},
            correlation_id=correlation_id,
            tamper_hash=digest,
            previous_hash=previous_hash,
            created_at=ts,
        )
        saved = await self._repo.append(entry)
        AUDIT_ENTRIES.labels(action=action, entity_type=entity_type).inc()
        return saved

    async def list_entries(self, **kwargs) -> list[AuditLog]:
        return await self._repo.list_entries(**kwargs)

    async def get_entry(self, entry_id: UUID) -> AuditLog | None:
        return await self._repo.get_by_id(entry_id)

    async def verify_integrity(self) -> dict:
        batch_limit = await self._settings.get_int(
            "monitoring.integrity_check_batch_size", default=5000
        )
        entries = await self._repo.iter_chain_ordered(limit=batch_limit)
        violations: list[dict] = []
        expected_previous: str | None = None

        for entry in entries:
            if entry.previous_hash != expected_previous:
                violations.append(
                    {
                        "entry_id": str(entry.id),
                        "issue": "previous_hash_mismatch",
                        "expected_previous": expected_previous,
                        "actual_previous": entry.previous_hash,
                    }
                )
            recomputed = compute_tamper_hash(
                previous_hash=entry.previous_hash,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                action=entry.action,
                before_state=entry.before_state,
                after_state=entry.after_state,
                timestamp=entry.timestamp,
            )
            if recomputed != entry.tamper_hash:
                violations.append(
                    {
                        "entry_id": str(entry.id),
                        "issue": "tamper_hash_mismatch",
                        "expected_hash": recomputed,
                        "stored_hash": entry.tamper_hash,
                    }
                )
            expected_previous = entry.tamper_hash

        first_date = entries[0].timestamp if entries else None
        last_date = entries[-1].timestamp if entries else None
        status = "valid" if not violations else "compromised"
        return {
            "integrity_status": status,
            "total_entries_checked": len(entries),
            "first_entry_date": first_date.isoformat() if first_date else None,
            "last_entry_date": last_date.isoformat() if last_date else None,
            "violations": violations,
        }

    async def export_rows(
        self,
        *,
        from_date: datetime | None,
        to_date: datetime | None,
        entity_type: str | None,
        actions: list[str] | None,
        fmt: str,
    ) -> tuple[str, bytes, str]:
        rows = await self._repo.list_entries(
            entity_type=entity_type,
            from_date=from_date,
            to_date=to_date,
            actions=actions,
            limit=10000,
        )
        export_id = str(uuid4())
        if fmt == "json":
            payload = [self._serialize_row(r) for r in rows]
            content = json.dumps({"export_id": export_id, "data": payload}, indent=2).encode()
            return export_id, content, "application/json"
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "id",
                "timestamp",
                "action",
                "entity_type",
                "entity_id",
                "case_number",
                "user_name",
                "tamper_hash",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": str(row.id),
                    "timestamp": row.timestamp.isoformat(),
                    "action": row.action,
                    "entity_type": row.entity_type,
                    "entity_id": str(row.entity_id) if row.entity_id else "",
                    "case_number": row.case_number or "",
                    "user_name": row.user_name or "",
                    "tamper_hash": format_tamper_hash(row.tamper_hash),
                }
            )
        return export_id, buffer.getvalue().encode("utf-8"), "text/csv"

    @staticmethod
    def _serialize_row(entry: AuditLog) -> dict:
        user = None
        if entry.user_id or entry.user_name:
            user = {
                "id": str(entry.user_id) if entry.user_id else None,
                "name": entry.user_name,
                "ip_address": str(entry.user_ip_address) if entry.user_ip_address else None,
            }
        return {
            "id": str(entry.id),
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": str(entry.entity_id) if entry.entity_id else None,
            "case_id": str(entry.case_id) if entry.case_id else None,
            "case_number": entry.case_number,
            "user": user,
            "before_state": entry.before_state,
            "after_state": entry.after_state,
            "metadata": entry.metadata_,
            "correlation_id": entry.correlation_id,
            "tamper_hash": format_tamper_hash(entry.tamper_hash),
            "previous_hash": (
                format_tamper_hash(entry.previous_hash) if entry.previous_hash else None
            ),
        }
