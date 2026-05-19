"""Password policy and history — `13` §5.2–§5.3."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import hash_password, password_matches_history
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.password_service import PasswordService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_password_history_rejects_reuse(db_session: AsyncSession):
    user_id = uuid.uuid4()
    first_hash = hash_password("FirstPassword1!")
    second_hash = hash_password("SecondPassword2!")
    user = User(
        id=user_id,
        username=f"hist_{uuid.uuid4().hex[:8]}",
        display_name="History User",
        email=f"hist_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=second_hash,
        role_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        status="active",
    )
    db_session.add(user)
    await db_session.flush()

    repo = UserRepository(db_session)
    await repo.append_password_history(user_id, first_hash)
    await db_session.commit()

    svc = PasswordService(db_session)
    with pytest.raises(ValueError, match="last 5 passwords"):
        await svc.change_password(user_id, "FirstPassword1!")

    new_hash = await svc.change_password(user_id, "ThirdPassword3!")
    assert new_hash != second_hash


def test_password_matches_history_unit():
    old = hash_password("OldPassword1!")
    assert password_matches_history("OldPassword1!", [old]) is True
    assert password_matches_history("NewPassword2!", [old]) is False
