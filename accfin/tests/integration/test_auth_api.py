"""Auth API acceptance tests — `12` §4 TestAuthAPI."""

import pyotp
import pytest
from httpx import AsyncClient

from app.models.user import User
from app.services import auth_service as auth_service_module
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user: User):
    response = await async_client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == test_user.username


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, test_user: User):
    response = await async_client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_rate_limit_after_failed_logins(async_client: AsyncClient):
    """In-memory rate limit (6 failures) — use unknown user to avoid DB lockout at 5."""
    auth_service_module._login_attempts.clear()
    for _ in range(6):
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "rate_limit_probe_user", "password": "wrong_password"},
        )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_refresh_and_logout(async_client: AsyncClient, test_user: User):
    login = await async_client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": TEST_PASSWORD},
    )
    tokens = login.json()
    refresh = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200
    assert "access_token" in refresh.json()

    logout = await async_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout.status_code == 204

    refresh_again = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_again.status_code == 401


@pytest.mark.asyncio
async def test_2fa_setup_verify_disable(async_client: AsyncClient, auth_headers: dict):
    setup = await async_client.post("/api/auth/2fa/setup", headers=auth_headers)
    assert setup.status_code == 200
    payload = setup.json()
    assert payload["secret"]
    assert payload["qr_code_uri"].startswith("otpauth://")
    assert len(payload["backup_codes"]) == 8

    code = pyotp.TOTP(payload["secret"]).now()
    verify = await async_client.post(
        "/api/auth/2fa/verify",
        headers=auth_headers,
        json={"totp_code": code, "secret": payload["secret"]},
    )
    assert verify.status_code == 200

    disable_code = pyotp.TOTP(payload["secret"]).now()
    disable = await async_client.post(
        "/api/auth/2fa/disable",
        headers=auth_headers,
        json={"totp_code": disable_code},
    )
    assert disable.status_code == 204


@pytest.mark.asyncio
async def test_approvals_approve_guard(
    async_client: AsyncClient, auth_headers: dict, accounts_manager_user: User
):
    ok = await async_client.get("/api/auth/session/me", headers=auth_headers)
    assert ok.status_code == 200

    clerk_login = await async_client.post(
        "/api/auth/login",
        json={"username": accounts_manager_user.username, "password": TEST_PASSWORD},
    )
    clerk_token = clerk_login.json()["access_token"]
    denied = await async_client.get(
        "/api/auth/session/me",
        headers={"Authorization": f"Bearer {clerk_token}"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "INSUFFICIENT_PERMISSION"


@pytest.mark.asyncio
async def test_change_password(async_client: AsyncClient, test_user: User):
    login = await async_client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    access = login.json()["access_token"]

    change = await async_client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "current_password": TEST_PASSWORD,
            "new_password": "NewValidPassword1!",
        },
    )
    assert change.status_code == 204

    old_login = await async_client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await async_client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": "NewValidPassword1!"},
    )
    assert new_login.status_code == 200
