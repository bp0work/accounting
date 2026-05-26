"""Client Admin company profile — same tenant resolution as dashboard."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from app.core.security.password import hash_password
from app.models.tenant_profile import TenantProfile
from app.models.user import User
from tests.conftest import TEST_PASSWORD

TENANT_MMLOGISTIX = uuid.UUID("00000000-0000-0000-0000-000000000200")
ROLE_CLIENT_ADMIN = uuid.UUID("00000000-0000-0000-0000-000000000008")
USER_SYSTEM_MMLOGISTIX = uuid.UUID("00000000-0000-0000-0000-000000000101")


@pytest.mark.integration
async def test_company_profile_for_system_mmlogistix_user(
    async_client: AsyncClient,
    db_session,
) -> None:
    """GET /api/admin/company-profile returns tenant profile for client_admin user."""
    user = await db_session.get(User, USER_SYSTEM_MMLOGISTIX)
    if user is None:
        pytest.skip("seed user system.mmlogistix not present")
    if user.tenant_id is None:
        user.tenant_id = TENANT_MMLOGISTIX
        await db_session.commit()

    profile = await db_session.get(TenantProfile, TENANT_MMLOGISTIX)
    if profile is None:
        profile = TenantProfile(
            tenant_id=TENANT_MMLOGISTIX,
            legal_name="MMLOGISTIX PTE. LTD.",
            uen="TEST-UEN-001",
            registered_address="1 Test Street",
            contact_email="acc.mmlogistix@bp0.work",
        )
        db_session.add(profile)
        await db_session.commit()
    else:
        profile.uen = profile.uen or "TEST-UEN-001"
        profile.registered_address = profile.registered_address or "1 Test Street"
        profile.contact_email = profile.contact_email or "acc.mmlogistix@bp0.work"
        await db_session.commit()

    login = await async_client.post(
        "/api/auth/login",
        json={"username": "system.mmlogistix", "password": TEST_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip(f"cannot login as system.mmlogistix: {login.status_code} {login.text}")

    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    dash = await async_client.get("/api/admin/dashboard", headers=headers)
    assert dash.status_code == 200
    company_check = next(c for c in dash.json()["checks"] if c["section"] == "company")
    assert company_check["complete"] is True

    resp = await async_client.get("/api/admin/company-profile", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["legal_name"]
    assert body["uen"] == "TEST-UEN-001"
    assert body["registered_address"]
    assert body["contact_email"]


@pytest.mark.integration
async def test_company_profile_uses_user_tenant_id(
    async_client: AsyncClient,
    db_session,
) -> None:
    """Profile API resolves tenant from users.tenant_id, not a hardcoded UUID."""
    suffix = uuid.uuid4().hex[:8]
    tenant_id = uuid.uuid4()
    from app.models.tenant import Tenant

    db_session.add(Tenant(id=tenant_id, display_name=f"Tenant {suffix}", slug=f"t-{suffix}"))
    db_session.add(
        TenantProfile(
            tenant_id=tenant_id,
            legal_name=f"Legal {suffix}",
            uen=f"UEN-{suffix}",
            registered_address="Addr",
            contact_email=f"ops-{suffix}@example.com",
        )
    )
    user = User(
        id=uuid.uuid4(),
        username=f"ca_co_{suffix}",
        display_name="CA Company",
        email=f"ca_co_{suffix}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=ROLE_CLIENT_ADMIN,
        tenant_id=tenant_id,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()

    login = await async_client.post(
        "/api/auth/login",
        json={"username": user.username, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await async_client.get("/api/admin/company-profile", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["legal_name"] == f"Legal {suffix}"
    assert resp.json()["uen"] == f"UEN-{suffix}"
