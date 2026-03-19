#!/usr/bin/env python
"""
scripts/check_migrations.py

Local migration integrity checker for Reach Developments Station.

Runs the same checks as ``tests/architecture/test_migration_integrity.py``
without requiring pytest, so developers can quickly validate their migration
work before committing.

Usage
-----
From the project root::

    python scripts/check_migrations.py

The script exits with code 0 on success and code 1 if any check fails.
Pass ``--verbose`` / ``-v`` for more detail in the output.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so ORM models can be imported.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_USE_COLOUR = sys.stdout.isatty()


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m" if _USE_COLOUR else text


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m" if _USE_COLOUR else text


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m" if _USE_COLOUR else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _USE_COLOUR else text


# ---------------------------------------------------------------------------
# Check result accumulator
# ---------------------------------------------------------------------------

class CheckResult:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed: list[str] = []
        self.warnings: list[str] = []
        self.failures: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    @property
    def success(self) -> bool:
        return not self.failures


class Report:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def print(self, verbose: bool = False) -> None:
        for result in self.results:
            status = _green("PASS") if result.success else _red("FAIL")
            warn_suffix = (
                f"  {_yellow(f'({len(result.warnings)} warning(s))')}"
                if result.warnings
                else ""
            )
            print(f"  [{status}] {result.name}{warn_suffix}")
            if verbose or not result.success:
                for msg in result.passed:
                    print(f"         {_green('✓')} {msg}")
                for msg in result.warnings:
                    print(f"         {_yellow('⚠')} {msg}")
                for msg in result.failures:
                    print(f"         {_red('✗')} {msg}")

    @property
    def all_passed(self) -> bool:
        return all(r.success for r in self.results)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_MIGRATIONS_DIR = os.path.join(_REPO_ROOT, "app", "db", "migrations")
_VERSIONS_DIR = os.path.join(_MIGRATIONS_DIR, "versions")
_ALEMBIC_INI = os.path.join(_REPO_ROOT, "alembic.ini")


def _migration_files() -> list[str]:
    return sorted(
        f
        for f in os.listdir(_VERSIONS_DIR)
        if f.endswith(".py") and not f.startswith("__")
    )


# ---------------------------------------------------------------------------
# Check 1: Migration chain structure
# ---------------------------------------------------------------------------

def check_chain_structure() -> CheckResult:
    result = CheckResult("Migration chain structure")
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(_ALEMBIC_INI)
        script = ScriptDirectory.from_config(cfg)

        heads = script.get_heads()
        if len(heads) == 1:
            result.ok(f"Single head: {heads[0]}")
        else:
            result.fail(f"Multiple heads detected: {heads} — run 'alembic merge heads'")

        bases = script.get_bases()
        if len(bases) == 1:
            result.ok(f"Single base: {bases[0]}")
        else:
            result.fail(f"Multiple bases detected: {bases}")

        revisions = list(script.walk_revisions())
        result.ok(f"Total revisions: {len(revisions)}")

        branching = []
        for rev in revisions:
            if isinstance(rev.down_revision, tuple):
                branching.append(rev.revision)
        if branching:
            result.fail(f"Merge revisions detected (non-linear): {branching}")
        else:
            result.ok("Chain is linear (no merge revisions)")

    except Exception as exc:
        result.fail(f"Alembic chain check failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Check 2: File completeness
# ---------------------------------------------------------------------------

def check_file_completeness() -> CheckResult:
    result = CheckResult("Migration file completeness")
    files = _migration_files()
    result.ok(f"Found {len(files)} migration files")

    missing_upgrade: list[str] = []
    missing_downgrade: list[str] = []
    missing_revision: list[str] = []
    sqlite_incompatible: list[str] = []

    for filename in files:
        path = os.path.join(_VERSIONS_DIR, filename)
        content = open(path).read()

        if not re.search(r"^def upgrade\s*\(", content, re.M):
            missing_upgrade.append(filename)
        if not re.search(r"^def downgrade\s*\(", content, re.M):
            missing_downgrade.append(filename)
        if not re.search(r"^revision\s*:\s*str\s*=", content, re.M):
            missing_revision.append(filename)

        # Detect SQLite-incompatible operations
        upgrade_match = re.search(
            r"^def upgrade\(\).*?(?=^def |\Z)", content, re.M | re.S
        )
        if upgrade_match:
            body = upgrade_match.group(0)
            has_constraint = bool(
                re.search(r"op\.create_unique_constraint|op\.drop_constraint", body)
            )
            uses_batch = "batch_alter_table" in body
            uses_guard = "dialect.name" in body
            if has_constraint and not uses_batch and not uses_guard:
                sqlite_incompatible.append(filename)

    if missing_upgrade:
        result.fail(f"Missing upgrade(): {missing_upgrade}")
    else:
        result.ok("All files have upgrade()")

    if missing_downgrade:
        result.fail(f"Missing downgrade(): {missing_downgrade}")
    else:
        result.ok("All files have downgrade()")

    if missing_revision:
        result.fail(f"Missing revision declaration: {missing_revision}")
    else:
        result.ok("All files have revision declaration")

    if sqlite_incompatible:
        result.warn(
            f"SQLite-incompatible ALTER operations (need PostgreSQL): "
            f"{sqlite_incompatible}"
        )
    else:
        result.ok("No unguarded SQLite-incompatible operations")

    return result


# ---------------------------------------------------------------------------
# Check 3: Attempt alembic upgrade head
# ---------------------------------------------------------------------------

def check_migration_run() -> CheckResult:
    result = CheckResult("Migration run (alembic upgrade head)")
    try:
        from alembic.config import Config
        from alembic import command as alembic_command
        from alembic.script import ScriptDirectory

        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = os.path.join(tmpdir, "check_migrations.db")
            db_url = f"sqlite:///{db_file}"

            cfg = Config(_ALEMBIC_INI)
            cfg.set_main_option("sqlalchemy.url", db_url)

            try:
                alembic_command.upgrade(cfg, "head")
            except NotImplementedError as exc:
                result.warn(
                    f"Upgrade blocked by SQLite limitation: {exc}. "
                    "Run against PostgreSQL for a complete validation."
                )
                return result
            except Exception as exc:
                result.fail(f"alembic upgrade head failed: {type(exc).__name__}: {exc}")
                return result

            # Verify the recorded head matches the declared head
            from sqlalchemy import create_engine, text

            script = ScriptDirectory.from_config(cfg)
            declared_head = script.get_current_head()

            engine = create_engine(db_url)
            with engine.connect() as conn:
                rows = conn.execute(text("SELECT version_num FROM alembic_version"))
                db_head = {row[0] for row in rows}

            if db_head == {declared_head}:
                result.ok(
                    f"Migrations applied cleanly; DB head={declared_head!r}"
                )
            else:
                result.fail(
                    f"DB head {db_head} does not match declared head {declared_head!r}"
                )

    except Exception as exc:
        result.fail(f"Migration run check failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Check 4: ORM table presence
# ---------------------------------------------------------------------------

def check_orm_tables() -> CheckResult:
    result = CheckResult("ORM table presence")
    try:
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.pool import StaticPool
        from app.db.base import Base
        import app.modules.auth.models  # noqa: F401
        import app.modules.buildings.models  # noqa: F401
        import app.modules.cashflow.models  # noqa: F401
        import app.modules.collections.models  # noqa: F401
        import app.modules.commission.models  # noqa: F401
        import app.modules.construction.models  # noqa: F401
        import app.modules.feasibility.models  # noqa: F401
        import app.modules.floors.models  # noqa: F401
        import app.modules.land.models  # noqa: F401
        import app.modules.payment_plans.models  # noqa: F401
        import app.modules.phases.models  # noqa: F401
        import app.modules.pricing.models  # noqa: F401
        import app.modules.pricing_attributes.models  # noqa: F401
        import app.modules.projects.models  # noqa: F401
        import app.modules.receivables.models  # noqa: F401
        import app.modules.registry.models  # noqa: F401
        import app.modules.reservations.models  # noqa: F401
        import app.modules.sales.models  # noqa: F401
        import app.modules.sales_exceptions.models  # noqa: F401
        import app.modules.settings.models  # noqa: F401
        import app.modules.units.models  # noqa: F401

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)

        actual_tables = set(inspector.get_table_names())
        expected_tables = set(Base.metadata.tables.keys())

        missing = expected_tables - actual_tables
        extra = actual_tables - expected_tables - {"alembic_version"}

        if missing:
            result.fail(f"Missing tables: {sorted(missing)}")
        else:
            result.ok(f"All {len(expected_tables)} ORM tables created successfully")

        if extra:
            result.warn(f"Extra tables in schema not in ORM: {sorted(extra)}")

        # Cross-check with migrations
        migration_tables: set[str] = set()
        for filename in _migration_files():
            content = open(os.path.join(_VERSIONS_DIR, filename)).read()
            found = re.findall(r'op\.create_table\(\s*["\'](\w+)["\']', content)
            migration_tables.update(found)

        orphaned = migration_tables - expected_tables
        unmigrated = expected_tables - migration_tables

        if orphaned:
            result.fail(f"Tables in migrations but not in ORM: {sorted(orphaned)}")
        if unmigrated:
            result.fail(f"Tables in ORM but not in any migration: {sorted(unmigrated)}")
        if not orphaned and not unmigrated:
            result.ok("Migration tables match ORM tables exactly")

    except Exception as exc:
        result.fail(f"ORM table check failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Check 5: Foreign-key topology
# ---------------------------------------------------------------------------

def check_foreign_keys() -> CheckResult:
    result = CheckResult("Foreign-key topology")
    try:
        from app.db.base import Base

        tables = Base.metadata.tables
        errors: list[str] = []

        for table_name, table in tables.items():
            for col in table.columns:
                for fk in col.foreign_keys:
                    target = fk.target_fullname
                    parts = target.split(".")
                    if len(parts) != 2:
                        errors.append(
                            f"{table_name}.{col.name}: malformed FK {target!r}"
                        )
                        continue
                    ref_table, ref_col = parts
                    if ref_table not in tables:
                        errors.append(
                            f"{table_name}.{col.name} → {target!r}: "
                            f"table {ref_table!r} does not exist"
                        )
                    elif ref_col not in tables[ref_table].c:
                        errors.append(
                            f"{table_name}.{col.name} → {target!r}: "
                            f"column {ref_col!r} not found in {ref_table!r}"
                        )

        if errors:
            for e in errors:
                result.fail(e)
        else:
            total_fks = sum(
                len(list(col.foreign_keys))
                for t in tables.values()
                for col in t.columns
            )
            result.ok(f"All {total_fks} FK references are valid")

    except Exception as exc:
        result.fail(f"FK topology check failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Check 6: Critical indexes
# ---------------------------------------------------------------------------

def check_indexes() -> CheckResult:
    result = CheckResult("Critical indexes")
    try:
        from app.db.base import Base

        tables = Base.metadata.tables
        critical = [
            ("phases", "ix_phases_project_id"),
            ("buildings", "ix_buildings_phase_id"),
            ("floors", "ix_floors_building_id"),
            ("units", "ix_units_floor_id"),
            ("sales_contracts", "ix_sales_contracts_unit_id"),
            ("reservations", "ix_reservations_unit_id"),
            ("payment_schedules", "ix_payment_schedules_contract_id"),
            ("registration_cases", "ix_registration_cases_unit_id"),
            ("construction_progress_updates", "ix_construction_progress_updates_milestone_id"),
            ("construction_scopes", "ix_construction_scopes_project_id"),
            ("cashflow_forecasts", "ix_cashflow_forecasts_project_id"),
            ("receivables", "ix_receivables_contract_id"),
            ("receivables", "ix_receivables_due_date"),
        ]
        missing: list[str] = []
        present: list[str] = []

        for table_name, index_name in critical:
            if table_name not in tables:
                missing.append(f"Table {table_name!r} not found")
                continue
            existing = {idx.name for idx in tables[table_name].indexes}
            if index_name not in existing:
                missing.append(f"{index_name} on {table_name}")
            else:
                present.append(index_name)

        if missing:
            for m in missing:
                result.fail(f"Missing index: {m}")
        result.ok(f"{len(present)}/{len(critical)} critical indexes present")

    except Exception as exc:
        result.fail(f"Index check failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reach Developments Station — migration integrity checker"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show all check details"
    )
    args = parser.parse_args(argv)

    print()
    print(_bold("═══ Migration Integrity Check ═══"))
    print(f"  Migrations dir : {_VERSIONS_DIR}")
    print()

    report = Report()

    checks = [
        check_chain_structure,
        check_file_completeness,
        check_migration_run,
        check_orm_tables,
        check_foreign_keys,
        check_indexes,
    ]

    for check_fn in checks:
        try:
            result = check_fn()
        except Exception as exc:
            result = CheckResult(check_fn.__name__)
            result.fail(f"Unexpected error: {exc}")
        report.add(result)

    print()
    report.print(verbose=args.verbose)

    total = len(report.results)
    passed = sum(1 for r in report.results if r.success)
    failed = total - passed
    warnings = sum(len(r.warnings) for r in report.results)

    print()
    if report.all_passed:
        verdict = _green("All checks passed")
        if warnings:
            verdict += f"  {_yellow(f'({warnings} warning(s))')}"
        print(f"  {verdict}")
    else:
        print(
            f"  {_red(f'{failed} check(s) failed')}, "
            f"{_green(f'{passed} passed')}"
            + (f", {_yellow(f'{warnings} warning(s)')}" if warnings else "")
        )
        print()
        print(
            "  See docs/03-technical/database-migrations.md for guidance on "
            "fixing migration issues."
        )
    print()

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
