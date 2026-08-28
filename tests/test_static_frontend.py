"""Static frontend serving contract.

Production routing is ``/api/v1/*`` to FastAPI and everything else to the
Next.js static export. The backend must also remain importable and testable when
that export has not been built.

These assertions are deliberately made through HTTP rather than by inspecting
FastAPI's route table: the observable behaviour is the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import FRONTEND_EXPORT_DIR, create_app

STATIC_MARKER = "<!doctype html><title>static export</title>"


def _build_export(root: Path) -> Path:
    export_dir = root / "out"
    export_dir.mkdir()
    (export_dir / "index.html").write_text(STATIC_MARKER, encoding="utf-8")
    return export_dir


def test_export_directory_points_at_the_next_build_output() -> None:
    """Given the configured path, then it is frontend/out at the repository root."""
    repo_root = Path(main.__file__).resolve().parents[1]

    assert repo_root / "frontend" / "out" == FRONTEND_EXPORT_DIR


def test_backend_serves_the_api_without_a_frontend_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Given no export directory, when the app runs, then the API still works."""
    monkeypatch.setattr(main, "FRONTEND_EXPORT_DIR", tmp_path / "absent")

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/").status_code == 404


def test_the_static_export_is_served_at_the_site_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Given an export directory, when the root is requested, then index.html is served."""
    monkeypatch.setattr(main, "FRONTEND_EXPORT_DIR", _build_export(tmp_path))

    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.text == STATIC_MARKER


def test_the_api_namespace_cannot_be_shadowed_by_static_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Given a static file on an API path, then the API answer still wins."""
    export_dir = _build_export(tmp_path)
    shadow = export_dir / "api" / "v1" / "health"
    shadow.mkdir(parents=True)
    (shadow / "live").write_text("STATIC SHADOW", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_EXPORT_DIR", export_dir)

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
