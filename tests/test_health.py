"""Health probe behaviour.

Given / When / Then, expressed against the public HTTP contract rather than
against implementation details.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import dispose_engine
from app.main import app
from tests.conftest import UNREACHABLE_DATABASE_SECRETS, UNREACHABLE_DATABASE_URL

LIVE_URL = "/api/v1/health/live"
READY_URL = "/api/v1/health/ready"


def test_liveness_reports_the_service_as_up(client: TestClient) -> None:
    """Given a running process, when liveness is probed, then it reports ok."""
    response = client.get(LIVE_URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": get_settings().APP_NAME}


def test_liveness_does_not_require_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an unreachable database, when liveness is probed, then it still reports ok."""
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DATABASE_URL)
    get_settings.cache_clear()
    dispose_engine()

    with TestClient(app) as client:
        response = client.get(LIVE_URL)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_ok_when_postgresql_is_reachable(
    postgres: None, client: TestClient
) -> None:
    """Given a reachable database, when readiness is probed, then it reports ok."""
    response = client.get(READY_URL)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": get_settings().APP_NAME,
        "database": "ok",
    }


def test_readiness_reports_503_when_postgresql_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given an unreachable database, when readiness is probed, then it fails safely."""
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DATABASE_URL)
    get_settings.cache_clear()
    dispose_engine()

    with TestClient(app) as client:
        response = client.get(READY_URL)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service dependencies are not ready."}


def test_readiness_failure_never_leaks_connection_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a readiness failure, then no credential or host detail reaches the client."""
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DATABASE_URL)
    get_settings.cache_clear()
    dispose_engine()

    with TestClient(app) as client:
        response = client.get(READY_URL)

    exposed = f"{response.text} {dict(response.headers)}"
    for secret in UNREACHABLE_DATABASE_SECRETS:
        assert secret not in exposed, f"readiness response leaked {secret!r}"
    assert "Traceback" not in exposed
    assert "psycopg" not in exposed
    assert "sqlalchemy" not in exposed.lower()


def test_health_routes_live_under_the_versioned_api_prefix(client: TestClient) -> None:
    """Given the reserved namespace, then health is only served beneath /api/v1."""
    assert get_settings().API_V1_PREFIX == "/api/v1"
    assert client.get("/health/live").status_code == 404
