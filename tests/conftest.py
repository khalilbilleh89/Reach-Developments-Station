"""Shared test fixtures.

Every test starts from freshly resolved configuration so that tests which
re-point ``DATABASE_URL`` cannot leak state into their neighbours.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import check_database_connection, dispose_engine
from app.main import app

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
def isolated_configuration() -> Iterator[None]:
    """Clear cached settings and engine around every test."""
    _reset_configuration()
    yield
    _reset_configuration()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """An HTTP client bound to the real application instance."""
    with TestClient(app) as test_client:
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
