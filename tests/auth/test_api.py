"""
Tests for the auth API endpoints.

Validates HTTP behaviour for registration, login, and the protected /me endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from app.modules.auth.security import create_access_token


# ---------------------------------------------------------------------------
# /register endpoint
# ---------------------------------------------------------------------------


def test_register_returns_token(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email_returns_409(client: TestClient):
    payload = {"email": "dup@example.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_invalid_email_returns_422(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /login endpoint
# ---------------------------------------------------------------------------


def test_login_success(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "secret_pw"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "secret_pw"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={"email": "pw@example.com", "password": "correct_pw"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "pw@example.com", "password": "wrong_pw1"},
    )
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "any_pass1"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /me endpoint
# ---------------------------------------------------------------------------


def test_me_returns_user_profile(client: TestClient):
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = reg_resp.json()["access_token"]

    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "roles" in data


def test_me_without_token_returns_401(client: TestClient):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_invalid_token_returns_401(client: TestClient):
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert resp.status_code == 401


def test_token_structure_contains_required_claims(client: TestClient):
    """JWT payload must contain sub and roles claims."""
    import jwt as _jwt
    from app.core.config import settings

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "claims@example.com", "password": "password123"},
    )
    token = reg_resp.json()["access_token"]
    payload = _jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert "sub" in payload
    assert "roles" in payload
    assert "exp" in payload
