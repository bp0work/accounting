from uuid import uuid4

import pytest

from app.core.jwt import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token


def test_access_token_roundtrip():
    user_id = uuid4()
    token, expires_in = create_access_token(
        user_id=user_id,
        role="finance_officer",
        permissions=["cases:read"],
    )
    assert expires_in == 900
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "cases:read" in payload["permissions"]


def test_refresh_token_roundtrip():
    user_id = uuid4()
    token, jti, _expires = create_refresh_token(user_id=user_id)
    payload = decode_refresh_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["jti"] == str(jti)
    assert payload["type"] == "refresh"


def test_wrong_type_rejected():
    user_id = uuid4()
    access, _ = create_access_token(user_id=user_id, role="x", permissions=[])
    with pytest.raises(Exception):
        decode_refresh_token(access)
