"""TokenData JWT payload — only user_id, role, permissions (`0.14.74`)."""

from uuid import uuid4

from app.schemas.auth import TokenData


def test_token_data_fields() -> None:
    token = TokenData(user_id=uuid4(), role="finance_manager", permissions=["approvals:approve"])
    assert set(token.model_fields) == {"user_id", "role", "permissions"}
