"""Segregation of duties via permission guards — `13` §5.7."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.dependencies import require_permission
from app.schemas.auth import TokenData


def make_token(permissions: list[str], role: str = "test_role") -> TokenData:
    return TokenData(user_id=uuid4(), role=role, permissions=permissions)


class TestSegregationOfDuties:
    GM_PERMISSIONS = [
        "cases:read",
        "cases:write",
        "approvals:read",
        "queues:read",
    ]

    FINANCE_OFFICER_PERMISSIONS = [
        "cases:read",
        "cases:write",
        "approvals:read",
        "approvals:approve",
        "journal-entries:read",
        "journal-entries:write",
    ]

    @pytest.mark.asyncio
    async def test_gm_cannot_approve_financial(self):
        user = make_token(self.GM_PERMISSIONS)
        checker = require_permission("approvals:approve")
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"]["code"] == "INSUFFICIENT_PERMISSION"

    @pytest.mark.asyncio
    async def test_gm_cannot_post_journal(self):
        user = make_token(self.GM_PERMISSIONS)
        checker = require_permission("journal-entries:write")
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_finance_officer_can_approve(self):
        user = make_token(self.FINANCE_OFFICER_PERMISSIONS)
        checker = require_permission("approvals:approve")
        result = await checker(user=user)
        assert result.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_permission_check_is_not_role_name_based(self):
        misconfigured_gm = TokenData(
            user_id=uuid4(),
            role="general_manager",
            permissions=["approvals:approve"],
        )
        checker = require_permission("approvals:approve")
        result = await checker(user=misconfigured_gm)
        assert result is not None
