"""Human-readable labels for case timeline `actor` (varchar 50)."""

from __future__ import annotations

import re
from uuid import UUID

from app.models.case import CaseTimeline
from app.models.user import User

_UUID_ACTOR_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_uuid_actor(actor: str) -> bool:
    return bool(_UUID_ACTOR_RE.match((actor or "").strip()))


def timeline_actor_label_for_user(user: User | None, *, fallback: str = "system") -> str:
    """Fit display_name / username / email into case_timeline.actor (50 chars)."""
    if user is None:
        return fallback[:50]
    for candidate in (user.display_name, user.username, user.email):
        if candidate and str(candidate).strip():
            return str(candidate).strip()[:50]
    return fallback[:50]


def resolve_timeline_actor_display(
    entry: CaseTimeline,
    users_by_id: dict[UUID, User],
) -> str:
    """Prefer linked user name; keep worker/system labels; fix stored UUID strings."""
    if entry.actor_user_id:
        user = users_by_id.get(entry.actor_user_id)
        if user is not None:
            return timeline_actor_label_for_user(user, fallback=entry.actor)
    if is_uuid_actor(entry.actor):
        return entry.actor
    return entry.actor
