"""
Tests for the auth service layer.

Validates password hashing, verification, JWT generation, role assignment,
and invalid credential handling.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.schemas import UserCreate, UserLogin
from app.modules.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth.service import AuthService


# ---------------------------------------------------------------------------
# Password utility tests
# ---------------------------------------------------------------------------


def test_hash_password_returns_non_plain():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert len(hashed) > 20


def test_verify_password_correct():
    hashed = hash_password("my_password")
    assert verify_password("my_password", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct_pw")
    assert verify_password("wrong_pw", hashed) is False


# ---------------------------------------------------------------------------
# JWT utility tests
# ---------------------------------------------------------------------------


def test_create_and_decode_token():
    token = create_access_token({"sub": "user-123", "roles": ["admin"]})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["roles"] == ["admin"]


def test_decode_invalid_token_raises_401():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not.a.valid.token")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# AuthService tests
# ---------------------------------------------------------------------------


def test_register_new_user(db_session: Session):
    svc = AuthService(db_session)
    token_resp = svc.register(UserCreate(email="user@example.com", password="password123"))
    assert token_resp.access_token
    assert token_resp.token_type == "bearer"
    payload = decode_access_token(token_resp.access_token)
    assert "sub" in payload


def test_register_duplicate_email_raises_409(db_session: Session):
    svc = AuthService(db_session)
    svc.register(UserCreate(email="dup@example.com", password="password123"))
    with pytest.raises(HTTPException) as exc_info:
        svc.register(UserCreate(email="dup@example.com", password="other_pw9"))
    assert exc_info.value.status_code == 409


def test_login_valid_credentials(db_session: Session):
    svc = AuthService(db_session)
    svc.register(UserCreate(email="login@example.com", password="secret_pw"))
    token_resp = svc.login(UserLogin(email="login@example.com", password="secret_pw"))
    assert token_resp.access_token


def test_login_wrong_password_raises_401(db_session: Session):
    svc = AuthService(db_session)
    svc.register(UserCreate(email="wrong@example.com", password="correct_pw"))
    with pytest.raises(HTTPException) as exc_info:
        svc.login(UserLogin(email="wrong@example.com", password="incorrect_pw"))
    assert exc_info.value.status_code == 401


def test_login_unknown_email_raises_401(db_session: Session):
    svc = AuthService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.login(UserLogin(email="ghost@example.com", password="any_pass1"))
    assert exc_info.value.status_code == 401


def test_get_current_user_returns_profile(db_session: Session):
    svc = AuthService(db_session)
    token_resp = svc.register(UserCreate(email="me@example.com", password="password1"))
    payload = decode_access_token(token_resp.access_token)
    user = svc.get_current_user(payload["sub"])
    assert user.email == "me@example.com"
    assert user.is_active is True


def test_assign_role_to_user(db_session: Session):
    svc = AuthService(db_session)
    token_resp = svc.register(UserCreate(email="role@example.com", password="password1"))
    payload = decode_access_token(token_resp.access_token)
    user_id = payload["sub"]

    svc.assign_role(user_id, "admin")
    user = svc.get_current_user(user_id)
    role_names = [r.name for r in user.roles]
    assert "admin" in role_names


def test_assign_same_role_twice_is_idempotent(db_session: Session):
    svc = AuthService(db_session)
    token_resp = svc.register(UserCreate(email="idem@example.com", password="password1"))
    payload = decode_access_token(token_resp.access_token)
    user_id = payload["sub"]

    svc.assign_role(user_id, "finance_user")
    svc.assign_role(user_id, "finance_user")  # should not raise or duplicate
    user = svc.get_current_user(user_id)
    role_names = [r.name for r in user.roles]
    assert role_names.count("finance_user") == 1
