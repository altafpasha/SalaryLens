"""
Unit tests for password hashing and JWT authentication
"""
import uuid
import pytest
from fastapi import HTTPException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password
)


def test_password_hashing():
    pw = "SuperSecretP@ssw0rd!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_flow():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    role = "reviewer"

    token = create_access_token(
        subject=str(user_id),
        organization_id=str(org_id),
        role=role,
    )
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["role"] == "reviewer"
    assert payload["iss"] == "salarylens-ai"


def test_invalid_jwt_token():
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not.a.valid.jwt.token")
    assert exc_info.value.status_code == 401
