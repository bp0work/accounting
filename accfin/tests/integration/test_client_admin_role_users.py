"""Client Admin key-role user provisioning."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.rbac import Role
from app.models.user import User
from app.core.security.password import hash_password

TEST_PASSWORD = "ChangeMeOnFirstLogin!"
ROLE_CLIENT_ADMIN = uuid.UUID("00000000-0000-0000-0000-000000000008")


@pytest.fixture
async def client_admin_headers(async_client: AsyncClient, db_session) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        username=f"ca_roles_{suffix}",
        display_name="Client Admin Roles UAT",
        email=f"ca_roles_{suffix}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=ROLE_CLIENT_ADMIN,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    response = await async_client.post(
        "/api/auth/login",
        json={"username": user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
async def test_upsert_accounts_manager_by_role(
    async_client: AsyncClient,
    client_admin_headers: dict[str, str],
    db_session,
) -> None:
    """PUT /admin/users/by-role/accounts_manager creates contact when no active user."""
    role_id = (
        await db_session.execute(select(Role.id).where(Role.name == "accounts_manager"))
    ).scalar_one()
    existing = (
        await db_session.execute(
            select(User).where(User.role_id == role_id, User.status == "active")
        )
    ).scalars().all()
    for u in existing:
        u.status = "inactive"
    await db_session.commit()

    resp = await async_client.put(
        "/api/users/by-role/accounts_manager",
        headers=client_admin_headers,
        json={
            "display_name": "mmlogistix Manager Accounts",
            "email": "acc.mmlogistix@bp0.work",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role_name"] == "accounts_manager"
    assert data["email"] == "acc.mmlogistix@bp0.work"
    assert data["display_name"] == "mmlogistix Manager Accounts"
    assert data["configured"] is True
    assert data["id"]

    listed = await async_client.get("/api/users", headers=client_admin_headers)
    assert listed.status_code == 200
    acc_row = next(r for r in listed.json() if r["role_name"] == "accounts_manager")
    assert acc_row["id"] == data["id"]
    assert acc_row["email"] == "acc.mmlogistix@bp0.work"
