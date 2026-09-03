"""Alembic baseline behaviour against PostgreSQL.

PR-MVP-00 promises a fresh migration history whose baseline creates no business
schema and reverses cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.database import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0000_mvp_baseline"
HEAD_REVISION = "0009_construction"


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "app" / "db" / "migrations"))
    return config


def _current_revision() -> str | None:
    with get_engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _public_tables() -> set[str]:
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


@pytest.fixture
def empty_database(postgres: None) -> None:
    """Reverse every migration so the next upgrade genuinely executes.

    Without this, a database already stamped at head makes ``upgrade()`` a no-op,
    and any assertion about what the migration produced would pass no matter what
    the revision actually contains.
    """
    command.downgrade(_alembic_config(), "base")


def test_the_history_round_trips_from_empty_to_head_and_back(postgres: None) -> None:
    """Given PostgreSQL, when every revision is applied and reversed, then it round-trips."""
    config = _alembic_config()

    command.upgrade(config, "head")
    assert _current_revision() == HEAD_REVISION

    command.downgrade(config, "base")
    assert _current_revision() is None

    command.upgrade(config, "head")
    assert _current_revision() == HEAD_REVISION


def test_baseline_creates_no_business_schema(empty_database: None) -> None:
    """Given an empty database, when the baseline is applied, then it adds no tables.

    Targets the baseline revision by name rather than ``head``: the point is
    what *this* revision does, and that must stay true as later revisions land.

    The fixture guarantees the upgrade really runs, so this measures the
    revision's own effect rather than whatever was already in the database. The
    assertion is on the delta, so an unrelated table left in a developer's test
    database is reported as such instead of being blamed on the migration.
    """
    before = _public_tables()

    command.upgrade(_alembic_config(), BASELINE_REVISION)

    created = _public_tables() - before
    assert created <= {"alembic_version"}, (
        f"the baseline migration created business tables: {sorted(created)}"
    )
    assert "alembic_version" in _public_tables()

    # Restore head so the rest of the suite still has its schema.
    command.upgrade(_alembic_config(), "head")


def test_baseline_is_the_single_root_of_the_migration_history(postgres: None) -> None:
    """Given the new history, then the baseline is its only root revision."""
    script = ScriptDirectory.from_config(_alembic_config())
    revisions = list(script.walk_revisions())

    assert [revision.revision for revision in revisions if revision.down_revision is None] == [
        BASELINE_REVISION
    ]
