"""
Runtime boot smoke tests.

Validates that the application imports correctly from app.main, the FastAPI
instance exists, and the root/health endpoints respond as expected.

These tests protect the canonical ASGI entrypoint (app.main:app) from
accidental regressions. They do not test domain logic.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app


def test_app_is_fastapi_instance():
    """The 'app' object exported from app.main must be a FastAPI instance."""
    assert isinstance(app, FastAPI)


def test_app_has_title():
    """The FastAPI application must have a non-empty title."""
    assert app.title and len(app.title) > 0


def test_root_endpoint_returns_200():
    """GET / should return HTTP 200 with basic service info."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "env" in data
    assert "status" in data
    assert data["status"] == "running"


def test_health_endpoint_returns_200():
    """GET /health should return HTTP 200 — confirms ASGI boot path is correct."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
