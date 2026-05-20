"""Integration tests for audit logs API — `05` §14."""

import pytest
from httpx import AsyncClient

from app.services.audit_service import AuditService
from tests.conftest import TEST_PASSWORD


@pytest.mark.integration
async def test_audit_list_requires_permission(async_client: AsyncClient, test_user):
    login = await async_client.post(
        "/auth/login",
        json={"username": test_user.username, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = await async_client.get(
        "/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_audit_integrity_and_login_chain(
    async_client: AsyncClient, auditor_user, db_session
):
    login = await async_client.post(
        "/auth/login",
        json={"username": auditor_user.username, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    integrity = await async_client.get("/audit-logs/integrity-check", headers=headers)
    assert integrity.status_code == 200
    body = integrity.json()
    assert body["integrity_status"] == "valid"
    assert body["total_entries_checked"] >= 1

    listed = await async_client.get("/audit-logs?action=login", headers=headers)
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert any(row["action"] == "login" for row in data)

    service = AuditService(db_session)
    export_id, content, _ = await service.export_rows(fmt="csv", from_date=None, to_date=None, entity_type=None, actions=["login"])
    assert export_id
    assert b"login" in content
