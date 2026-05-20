"""Shared pytest fixtures — Phase 2 auth integration."""

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import get_settings
from app.core.security.password import hash_password
from app.main import app
from app.models.user import User

_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path)

_db_url = os.getenv("FINANCE_DATABASE_URL", "")
if "@db:" in _db_url:
    os.environ["FINANCE_DATABASE_URL"] = _db_url.replace("@db:", "@localhost:")
if os.getenv("FINANCE_REDIS__HOST") == "redis":
    os.environ["FINANCE_REDIS__HOST"] = "localhost"

if os.getenv("FINANCE_PRIVACY_ENCRYPTION_KEY", "").startswith("["):
    os.environ["FINANCE_PRIVACY_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
if os.getenv("FINANCE_JWT__SECRET", "").startswith("["):
    os.environ["FINANCE_JWT__SECRET"] = "test-jwt-secret-key-32-bytes-minimum!!"
if not os.getenv("FINANCE_INTERNAL_CRON__TOKEN") or os.getenv(
    "FINANCE_INTERNAL_CRON__TOKEN", ""
).startswith("["):
    os.environ["FINANCE_INTERNAL_CRON__TOKEN"] = "test-cron-token"
if not os.getenv("FINANCE_MAIL_ACTION__SECRET") or os.getenv(
    "FINANCE_MAIL_ACTION__SECRET", ""
).startswith("["):
    os.environ["FINANCE_MAIL_ACTION__SECRET"] = "test-mail-action-secret"
if not os.getenv("FINANCE_HASH_SECRET") or os.getenv("FINANCE_HASH_SECRET", "").startswith("["):
    os.environ["FINANCE_HASH_SECRET"] = "test-hash-secret-32-bytes-minimum!!"

get_settings.cache_clear()

ROLE_FINANCE_OFFICER = uuid.UUID("00000000-0000-0000-0000-000000000004")
ROLE_ACCOUNTS_CLERK = uuid.UUID("00000000-0000-0000-0000-000000000005")
ROLE_AUDITOR = uuid.UUID("00000000-0000-0000-0000-000000000006")

TEST_PASSWORD = "CorrectHorseBattery1!"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: tests requiring PostgreSQL (set FINANCE_DATABASE_URL)",
    )


def _database_configured() -> bool:
    return bool(os.getenv("FINANCE_DATABASE_URL"))


@pytest.fixture(autouse=True)
def _fake_redis() -> None:
    try:
        import fakeredis.aioredis
    except ImportError:
        return
    from app.core import redis_client

    redis_client._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
async def _reset_db_engine() -> AsyncGenerator[None, None]:
    """Avoid asyncpg 'different loop' errors when pytest creates new event loops."""
    yield
    if database._engine is not None:
        await database._engine.dispose()
    database._engine = None
    database._session_factory = None
    from app.core import redis_client

    redis_client._redis = None
    get_settings.cache_clear()
    from app.core.crypto import reset_fernet_cache

    reset_fernet_cache()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    if not _database_configured():
        pytest.skip("FINANCE_DATABASE_URL not set")
    factory = database.get_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    if not _database_configured():
        pytest.skip("FINANCE_DATABASE_URL not set")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        username=f"pytest_{suffix}",
        display_name="Pytest User",
        email=f"pytest_{suffix}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=ROLE_FINANCE_OFFICER,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def clerk_user(db_session: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        username=f"clerk_{suffix}",
        display_name="Clerk User",
        email=f"clerk_{suffix}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=ROLE_ACCOUNTS_CLERK,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def auditor_user(db_session: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        username=f"auditor_{suffix}",
        display_name="Auditor User",
        email=f"auditor_{suffix}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=ROLE_AUDITOR,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def auditor_auth_headers(async_client: AsyncClient, auditor_user: User) -> dict[str, str]:
    response = await async_client.post(
        "/auth/login",
        json={"username": auditor_user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers(async_client: AsyncClient, test_user: User) -> dict[str, str]:
    response = await async_client.post(
        "/auth/login",
        json={"username": test_user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
