"""Alembic baseline behaviour against PostgreSQL.

PR-MVP-00 promises a fresh migration history whose baseline creates no business
schema and reverses cleanly.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.database import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0000_mvp_baseline"


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


def test_baseline_upgrades_downgrades_and_upgrades_again(postgres: None) -> None:
    """Given PostgreSQL, when the baseline is applied and reversed, then it round-trips."""
    config = _alembic_config()

    command.upgrade(config, "head")
    assert _current_revision() == BASELINE_REVISION

    command.downgrade(config, "base")
    assert _current_revision() is None

    command.upgrade(config, "head")
    assert _current_revision() == BASELINE_REVISION


def test_baseline_creates_no_business_schema(postgres: None) -> None:
    """Given the baseline at head, then only Alembic bookkeeping exists."""
    command.upgrade(_alembic_config(), "head")

    assert _public_tables() == {"alembic_version"}


def test_baseline_is_the_single_root_of_the_migration_history(postgres: None) -> None:
    """Given the new history, then the baseline is its only root revision."""
    script = ScriptDirectory.from_config(_alembic_config())
    revisions = list(script.walk_revisions())

    assert [revision.revision for revision in revisions if revision.down_revision is None] == [
        BASELINE_REVISION
    ]
