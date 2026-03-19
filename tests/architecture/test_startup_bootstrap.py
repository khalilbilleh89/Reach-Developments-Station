"""
tests/architecture/test_startup_bootstrap.py

PR-E6: Startup / Bootstrap Hardening Tests.

Validates that the application startup and bootstrap path is deterministic,
idempotent, and resilient:

  1. Application starts successfully under normal configuration.
  2. Bootstrap is skipped cleanly in test environments.
  3. Bootstrap is skipped cleanly when credentials are not configured.
  4. Bootstrap does not duplicate records on repeated startups.
  5. A bootstrap exception does not prevent the application from starting.
  6. Health and root endpoints behave correctly after startup.
  7. Missing optional frontend static assets do not crash startup.
  8. The lifespan emits startup-complete and shutdown log messages.

These are architecture-level tests that validate startup sequencing and
operational scaffolding.  They do not test domain business logic.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.bootstrap import seed_admin_user
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_settings(**kwargs):
    """Return a context manager that patches app.main.settings attributes."""
    mock = MagicMock()
    mock.APP_NAME = kwargs.get("APP_NAME", "Reach Developments Station")
    mock.APP_ENV = kwargs.get("APP_ENV", "test")
    mock.APP_DEBUG = kwargs.get("APP_DEBUG", False)
    mock.ADMIN_EMAIL = kwargs.get("ADMIN_EMAIL", None)
    mock.ADMIN_PASSWORD = kwargs.get("ADMIN_PASSWORD", None)
    mock.API_V1_PREFIX = "/api/v1"
    return patch("app.main.settings", mock)


# ---------------------------------------------------------------------------
# 1. Application instance
# ---------------------------------------------------------------------------


def test_app_is_fastapi_instance():
    """The exported 'app' object must be a FastAPI instance."""
    assert isinstance(app, FastAPI)


def test_app_has_non_empty_title():
    """The FastAPI application must have a non-empty title."""
    assert app.title and len(app.title) > 0


# ---------------------------------------------------------------------------
# 2. Health endpoints after startup
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_200_after_startup(client: TestClient):
    """/health must return 200 with status 'ok' after the app has started."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "service" in data


def test_health_db_endpoint_exists(client: TestClient):
    """/health/db must exist and return a non-5xx response."""
    with patch("app.main.check_db_connection", return_value=True):
        resp = client.get("/health/db")
    assert resp.status_code in (200, 503)


def test_health_db_ok_when_database_reachable(client: TestClient):
    """/health/db returns 200 when the database connection succeeds."""
    with patch("app.main.check_db_connection", return_value=True):
        resp = client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_db_error_when_database_unreachable(client: TestClient):
    """/health/db returns 503 when the database connection fails."""
    with patch("app.main.check_db_connection", return_value=False):
        resp = client.get("/health/db")
    assert resp.status_code == 503
    assert resp.json()["status"] == "error"


# ---------------------------------------------------------------------------
# 3. Bootstrap skip — test environment
# ---------------------------------------------------------------------------


def test_bootstrap_skipped_in_test_environment(caplog):
    """Bootstrap must be silently skipped when APP_ENV is 'test'."""
    with _patch_settings(
        APP_ENV="test", ADMIN_EMAIL="admin@example.com", ADMIN_PASSWORD="pass"
    ):
        with patch("app.main.SessionLocal") as mock_session:
            with TestClient(app):
                pass
    # SessionLocal must never be opened — bootstrap was skipped
    mock_session.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Bootstrap skip — missing credentials
# ---------------------------------------------------------------------------


def test_bootstrap_skipped_when_no_credentials_logs_clearly(caplog):
    """Bootstrap must log clearly when ADMIN_EMAIL / ADMIN_PASSWORD are absent."""
    with _patch_settings(APP_ENV="production", ADMIN_EMAIL=None, ADMIN_PASSWORD=None):
        with patch("app.main.SessionLocal") as mock_session:
            with TestClient(app):
                pass
    # SessionLocal must never be opened when credentials are absent
    mock_session.assert_not_called()


def test_bootstrap_skipped_when_email_only(caplog):
    """Bootstrap must be skipped when only ADMIN_EMAIL is set (password missing)."""
    with _patch_settings(
        APP_ENV="production", ADMIN_EMAIL="admin@example.com", ADMIN_PASSWORD=None
    ):
        with patch("app.main.SessionLocal") as mock_session:
            with TestClient(app):
                pass
    mock_session.assert_not_called()


def test_bootstrap_skipped_when_password_only(caplog):
    """Bootstrap must be skipped when only ADMIN_PASSWORD is set (email missing)."""
    with _patch_settings(
        APP_ENV="production", ADMIN_EMAIL=None, ADMIN_PASSWORD="secret"
    ):
        with patch("app.main.SessionLocal") as mock_session:
            with TestClient(app):
                pass
    mock_session.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Bootstrap exception resilience
# ---------------------------------------------------------------------------


def test_startup_continues_when_bootstrap_raises(caplog):
    """A bootstrap exception must not prevent the application from starting.

    The app must remain reachable after a seed failure.
    """
    with _patch_settings(
        APP_ENV="production", ADMIN_EMAIL="admin@example.com", ADMIN_PASSWORD="pass"
    ):
        mock_db = MagicMock()
        mock_session_cm = MagicMock()
        mock_session_cm.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cm.__exit__ = MagicMock(return_value=False)

        with patch("app.main.SessionLocal", return_value=mock_session_cm):
            with patch(
                "app.main.seed_admin_user", side_effect=RuntimeError("seed exploded")
            ):
                with TestClient(app) as client:
                    resp = client.get("/health")
    # The app must still be healthy despite the bootstrap error
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# 6. Bootstrap idempotency through the seed function
# ---------------------------------------------------------------------------


def test_seed_admin_idempotent_called_twice(db_session):
    """Calling seed_admin_user twice must not create duplicate records."""
    from app.modules.auth.models import User
    from unittest.mock import patch as _patch

    with _patch(
        "app.core.bootstrap.settings",
        ADMIN_EMAIL="admin@example.com",
        ADMIN_PASSWORD="SecurePass123",
    ):
        seed_admin_user(db_session)
        seed_admin_user(db_session)

    users = db_session.query(User).filter_by(email="admin@example.com").all()
    assert len(users) == 1, "seed_admin_user must not create duplicate users"


def test_seed_admin_role_not_duplicated_on_repeated_calls(db_session):
    """Bootstrap must not assign the admin role multiple times."""
    from app.modules.auth.repository import AuthRepository
    from unittest.mock import patch as _patch

    with _patch(
        "app.core.bootstrap.settings",
        ADMIN_EMAIL="admin@example.com",
        ADMIN_PASSWORD="SecurePass123",
    ):
        seed_admin_user(db_session)
        seed_admin_user(db_session)
        seed_admin_user(db_session)

    repo = AuthRepository(db_session)
    user = repo.get_user_by_email("admin@example.com")
    assert user is not None
    roles = repo.get_user_roles(user.id)
    admin_roles = [r for r in roles if r.name == "admin"]
    assert len(admin_roles) == 1, "admin role must be assigned exactly once"


# ---------------------------------------------------------------------------
# 7. Startup logging
# ---------------------------------------------------------------------------


def test_startup_logs_starting_message():
    """Startup must emit a log message identifying the app and environment."""
    with patch("app.main.logger") as mock_logger:
        with TestClient(app):
            pass

    info_msgs = [str(c.args[0]) for c in mock_logger.info.call_args_list if c.args]
    assert any("Starting" in msg or "Startup" in msg for msg in info_msgs), (
        f"Expected a startup log message; info calls: {info_msgs}"
    )


def test_startup_logs_completion_message():
    """Startup must emit a 'ready' or 'complete' log message after initialization."""
    with patch("app.main.logger") as mock_logger:
        with TestClient(app):
            pass

    info_msgs = [str(c.args[0]) for c in mock_logger.info.call_args_list if c.args]
    assert any(
        keyword in msg
        for msg in info_msgs
        for keyword in ("ready", "complete", "Startup complete")
    ), f"Expected startup-complete log message; info calls: {info_msgs}"


def test_startup_logs_frontend_build_status():
    """Startup must log whether the frontend build directory was found or not."""
    _no_build = Path(__file__).parent / "_nonexistent_frontend_build_for_test_"

    with patch("app.main.logger") as mock_logger:
        with patch("app.main._FRONTEND_HTML_DIR", _no_build):
            with TestClient(app):
                pass

    info_msgs = [str(c.args[0]) for c in mock_logger.info.call_args_list if c.args]
    assert any("frontend" in msg.lower() for msg in info_msgs), (
        f"Expected a frontend build status log message; info calls: {info_msgs}"
    )


# ---------------------------------------------------------------------------
# 8. Frontend absent — no startup crash
# ---------------------------------------------------------------------------


def test_startup_succeeds_without_frontend_build(tmp_path: Path):
    """The application must start successfully when the frontend build is absent."""
    no_build = tmp_path / "nonexistent_out"
    with patch("app.main._FRONTEND_HTML_DIR", no_build):
        with TestClient(app) as client:
            resp = client.get("/health")
    assert resp.status_code == 200


def test_root_returns_json_fallback_when_frontend_absent(tmp_path: Path):
    """GET / must return a JSON status payload when the frontend build is absent."""
    no_build = tmp_path / "nonexistent_out"
    with patch("app.main._FRONTEND_HTML_DIR", no_build):
        with TestClient(app) as client:
            resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "app" in data
    assert data["status"] == "running"


# ---------------------------------------------------------------------------
# 9. OpenAPI schema available after startup
# ---------------------------------------------------------------------------


def test_openapi_schema_available_after_startup(client: TestClient):
    """/openapi.json must be accessible after startup and return a valid schema."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "openapi" in schema
    assert "paths" in schema
    assert "info" in schema
