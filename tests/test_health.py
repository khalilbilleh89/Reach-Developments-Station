"""Health probe behaviour.

Given / When / Then, expressed against the public HTTP contract rather than
against implementation details.
"""

from __future__ import annotations

import socket
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core import database
from app.core.config import get_settings
from app.core.database import (
    check_database_connection,
    dispose_engine,
)
from app.main import create_app
from tests.conftest import UNREACHABLE_DATABASE_SECRETS, UNREACHABLE_DATABASE_URL

API_PREFIX = "/api/v1"
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

    with TestClient(create_app()) as client:
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

    with TestClient(create_app()) as client:
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

    with TestClient(create_app()) as client:
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


def test_unmatched_api_paths_answer_with_json_not_the_frontend_404(
    client: TestClient,
) -> None:
    """Given a mistyped API path, then the client gets the JSON error contract.

    StaticFiles(html=True) answers any unmatched path with the frontend's 404
    page, so without a namespace guard an API client would receive HTML.
    """
    for path in (f"{API_PREFIX}/projects", f"{API_PREFIX}/health/liv", f"{API_PREFIX}/"):
        response = client.get(path)

        assert response.status_code == 404, path
        assert response.headers["content-type"].startswith("application/json"), path
        assert response.json() == {"detail": "Not Found."}, path


def test_the_namespace_guard_does_not_shadow_real_routes(client: TestClient) -> None:
    """Given registered endpoints, then the catch-all never intercepts them."""
    assert client.get(LIVE_URL).status_code == 200
    assert client.get(f"{API_PREFIX}/openapi.json").status_code == 200


def test_readiness_probe_is_bounded_when_postgresql_never_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a server that accepts TCP but never replies, then the probe gives up.

    libpq waits forever by default. Readiness runs in the same threadpool that
    serves liveness, so an unbounded probe eventually takes liveness down too.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(8)
        port = listener.getsockname()[1]

        # libpq clamps connect_timeout below 2 seconds up to 2.
        monkeypatch.setattr(database, "_CONNECT_TIMEOUT_SECONDS", 2)
        monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://u:p@127.0.0.1:{port}/d")
        get_settings.cache_clear()
        dispose_engine()

        started = time.monotonic()
        with pytest.raises(SQLAlchemyError):
            check_database_connection()
        elapsed = time.monotonic() - started
    finally:
        listener.close()

    assert elapsed < 20, f"probe was not bounded; it took {elapsed:.1f}s"
