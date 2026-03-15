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
# Uses a relative path anchored to this file so it is portable across platforms.
_NO_BUILD = Path(__file__).parent / "_nonexistent_frontend_build_"


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


# ---------------------------------------------------------------------------
# Asset-vs-HTML routing tests
# ---------------------------------------------------------------------------

def test_known_asset_returns_file_when_present(tmp_path: Path) -> None:
    """A path with a file extension that exists in the build is served directly.

    Simulates frontend/.next/server/app/favicon.ico being present.
    """
    favicon = tmp_path / "favicon.ico"
    favicon.write_bytes(b"\x00\x00\x01\x00")  # minimal .ico header

    with patch("app.main._FRONTEND_HTML_DIR", tmp_path):
        client = TestClient(app)
        response = client.get("/favicon.ico")
    # File exists → served directly, not via HTML fallback
    assert response.status_code == 200
    assert "text/html" not in response.headers.get("content-type", "")


def test_unknown_asset_returns_404(tmp_path: Path) -> None:
    """A path with a file extension that is NOT in the build returns 404.

    Verifies that missing assets do not silently fall back to index.html.
    """
    # Provide a valid build dir with root index.html so the fallback would
    # kick in if the extension guard were absent.
    (tmp_path / "index.html").write_text("<html><body>root</body></html>")

    with patch("app.main._FRONTEND_HTML_DIR", tmp_path):
        client = TestClient(app)
        response = client.get("/nonexistent.png")
    assert response.status_code == 404


def test_extensionless_dynamic_route_falls_back_to_html(tmp_path: Path) -> None:
    """An extensionless dynamic route still resolves through the SPA fallback chain.

    /sales/123 should serve sales.html (parent segment fallback), not 404.
    """
    sales_html = tmp_path / "sales.html"
    sales_html.write_text("<html><body>sales</body></html>")

    with patch("app.main._FRONTEND_HTML_DIR", tmp_path):
        client = TestClient(app)
        response = client.get("/sales/123")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
