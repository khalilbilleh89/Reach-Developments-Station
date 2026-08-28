"""Shared test fixtures.

The suite pins its own configuration so that a developer's shell, a stray
``.env`` file or a CI job's environment cannot change what the tests assert.
``DATABASE_URL`` is the single intentional external input: it must point at a
reachable throwaway PostgreSQL database.

Applications under test are built through :func:`app.main.create_app` rather
than the module-level instance, so each test sees the configuration pinned
below instead of whatever was in scope at import time.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import check_database_connection, dispose_engine
from app.main import create_app

PINNED_TEST_CONFIG = {
    "APP_NAME": "reach-developments-station",
    "APP_ENV": "test",
    "APP_DEBUG": "false",
    "API_V1_PREFIX": "/api/v1",
}

#: A deliberately unroutable PostgreSQL target with distinctive credentials, so
#: that leak assertions have something unmistakable to look for.
UNREACHABLE_DATABASE_URL = (
    "postgresql+psycopg://probe_user:pr0be-s3cret@127.0.0.1:59999/probe_database"
)
UNREACHABLE_DATABASE_SECRETS = (
    "probe_user",
    "pr0be-s3cret",
    "59999",
    "probe_database",
)


def _reset_configuration() -> None:
    get_settings.cache_clear()
    dispose_engine()


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin configuration and clear cached settings and engine around every test."""
    for name, value in PINNED_TEST_CONFIG.items():
        monkeypatch.setenv(name, value)
    _reset_configuration()
    yield
    _reset_configuration()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """An HTTP client bound to a freshly built application."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def postgres() -> None:
    """Require a reachable test database.

    Fails rather than skips: a silently skipped database test in CI is worse
    than a red build.
    """
    try:
        check_database_connection()
    except SQLAlchemyError as exc:
        pytest.fail(
            "This test requires PostgreSQL. Point DATABASE_URL at a reachable test "
            f"database before running pytest (got {type(exc).__name__})."
        )
