"""
Runtime boot smoke tests.

Validates that the application imports correctly from app.main, the FastAPI
instance exists, and key endpoints respond as expected.

These tests protect the canonical ASGI entrypoint (app.main:app) from
accidental regressions. They do not test domain logic.
"""

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app

# A path that is guaranteed not to exist, used to simulate an absent frontend build.
_NO_BUILD = Path("/tmp/nonexistent-frontend-build-path")


def test_app_is_fastapi_instance():
    """The 'app' object exported from app.main must be a FastAPI instance."""
    assert isinstance(app, FastAPI)


def test_app_has_title():
    """The FastAPI application must have a non-empty title."""
    assert app.title and len(app.title) > 0


def test_root_endpoint_returns_200():
    """GET / should return HTTP 200 in all environments.

    When the frontend build is present it serves an HTML document.
    When absent it returns the JSON status fallback.  Either is acceptable —
    this test validates only that the server responds with 200.
    """
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_root_endpoint_json_fallback_when_no_build():
    """GET / returns a JSON status payload when the frontend build is absent."""
    with patch("app.main._FRONTEND_HTML_DIR", _NO_BUILD):
        client = TestClient(app)
        response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "status" in data
    assert data["status"] == "running"


def test_root_endpoint_fallback_production_omits_debug_fields():
    """JSON fallback at GET / in production mode must not expose env or docs."""
    with patch("app.main._FRONTEND_HTML_DIR", _NO_BUILD):
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


def test_root_endpoint_fallback_debug_includes_debug_fields():
    """JSON fallback at GET / in debug mode should include env and docs fields."""
    with patch("app.main._FRONTEND_HTML_DIR", _NO_BUILD):
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
