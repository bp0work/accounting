"""Local attachment storage (hot path) — Supabase in production per `06` §7.5."""

from pathlib import Path
from uuid import UUID

from app.core.config import get_settings


def attachment_dir(email_id: UUID) -> Path:
    base = Path(get_settings().attachment_storage_path)
    path = base / str(email_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_attachment(*, email_id: UUID, filename: str, content: bytes) -> str:
    safe_name = Path(filename).name
    target = attachment_dir(email_id) / safe_name
    target.write_bytes(content)
    return str(target.relative_to(Path(get_settings().attachment_storage_path)))
