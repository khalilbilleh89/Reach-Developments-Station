"""Interactive API documentation exposure.

PR-MVP-00 left ``/docs`` public because only health probes existed. Now that
authentication and governance administration do, the schema enumerates every
administrative endpoint and payload for an unauthenticated reader, so it is
withheld in production.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

DOC_PATHS = ("/docs", "/redoc", "/api/v1/openapi.json")


@pytest.fixture
def production_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DEBUG", "false")
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.mark.parametrize("path", DOC_PATHS)
def test_documentation_is_available_outside_production(path: str) -> None:
    """Given development, then the schema and its viewers are served."""
    response = TestClient(create_app()).get(path)

    assert response.status_code == 200


@pytest.mark.parametrize("path", DOC_PATHS)
def test_documentation_is_withheld_in_production(production_client: TestClient, path: str) -> None:
    """Given production, then no schema or viewer is reachable."""
    response = production_client.get(path)

    assert response.status_code == 404
    # The API namespace guard answers for /api/v1/openapi.json; the root-level
    # viewers fall through to the static export. Either way, nothing is served.
    assert "swagger" not in response.text.casefold()
    assert "redoc" not in response.text.casefold()
    assert "openapi" not in response.text.casefold()


def test_the_api_still_works_in_production(production_client: TestClient) -> None:
    """Given production, then withholding docs has not broken the API itself."""
    response = production_client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
