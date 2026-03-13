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
    """GET / should return HTTP 200 with basic service info in all modes."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "status" in data
    assert data["status"] == "running"


def test_root_endpoint_production_omits_debug_fields():
    """GET / in production mode (APP_DEBUG=False) must not expose env or docs."""
    from unittest.mock import patch

    with patch("app.main.settings") as mock_settings:
        mock_settings.APP_NAME = "Reach Developments Station"
        mock_settings.APP_ENV = "production"
        mock_settings.APP_DEBUG = False
        client = TestClient(app)
        response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "env" not in data
    assert "docs" not in data


def test_root_endpoint_debug_includes_debug_fields():
    """GET / in debug mode (APP_DEBUG=True) should include env and docs fields."""
    from unittest.mock import patch

    with patch("app.main.settings") as mock_settings:
        mock_settings.APP_NAME = "Reach Developments Station"
        mock_settings.APP_ENV = "development"
        mock_settings.APP_DEBUG = True
        client = TestClient(app)
        response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "env" in data
    assert "docs" in data


def test_health_endpoint_returns_200():
    """GET /health should return HTTP 200 — confirms ASGI boot path is correct."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
