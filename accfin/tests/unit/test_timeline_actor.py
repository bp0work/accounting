"""Unit tests — timeline actor display labels."""

from uuid import UUID

from app.models.user import User
from app.services.timeline_actor import (
    is_uuid_actor,
    resolve_timeline_actor_display,
    timeline_actor_label_for_user,
)


def test_is_uuid_actor():
    assert is_uuid_actor("00000000-0000-0000-0000-000000000105")
    assert not is_uuid_actor("ap-worker")
    assert not is_uuid_actor("Finance Manager")


def test_timeline_actor_label_prefers_display_name():
    user = User(
        id=UUID("00000000-0000-0000-0000-000000000105"),
        username="finmgr",
        display_name="Marc Finance",
        email="fin@example.com",
        password_hash="x",
        role_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    assert timeline_actor_label_for_user(user) == "Marc Finance"


def test_timeline_actor_label_truncates_to_50():
    long_name = "A" * 80
    user = User(
        id=UUID("00000000-0000-0000-0000-000000000105"),
        username="u",
        display_name=long_name,
        email="e@example.com",
        password_hash="x",
        role_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    assert len(timeline_actor_label_for_user(user)) == 50


def test_resolve_timeline_actor_display_from_user_id():
    user_id = UUID("00000000-0000-0000-0000-000000000105")
    user = User(
        id=user_id,
        username="finmgr",
        display_name="Marc Finance",
        email="fin@example.com",
        password_hash="x",
        role_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    class _Entry:
        actor = str(user_id)
        actor_user_id = user_id

    assert (
        resolve_timeline_actor_display(_Entry(), {user_id: user}) == "Marc Finance"
    )
