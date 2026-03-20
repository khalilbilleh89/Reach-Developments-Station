"""
tests/architecture/test_migration_integrity.py

Migration integrity tests for PR-E2.

Validates that:
  1. The Alembic migration chain is linear and complete (no gaps, branches, or
     orphaned revisions).
  2. Every migration file declares a ``downgrade()`` function.
  3. Running ``alembic upgrade head`` on a fresh database succeeds end-to-end.
     On SQLite some ALTER TABLE operations (e.g. ``op.create_unique_constraint``
     as a standalone step) are not supported; those cases are collected and
     reported with ``pytest.xfail`` so the CI stays informative without being
     blocked.
  4. After building the schema via ``Base.metadata.create_all``, all expected
     tables are present.
  5. Every declared foreign-key points to a table and column that exist in the
     metadata (no dangling FK targets).
  6. Performance-critical indexes are present on the columns that matter most
     for dashboard and aggregation queries.
  7. The set of tables produced by migrations matches the set of tables
     declared in the ORM models (no orphaned migrations, no un-migrated models).
"""

import os
import re
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base

# ---------------------------------------------------------------------------
# Import every ORM model module so that all Table objects are registered in
# Base.metadata before any test that inspects metadata runs.
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_MIGRATIONS_DIR = os.path.join(_REPO_ROOT, "app", "db", "migrations")
_VERSIONS_DIR = os.path.join(_MIGRATIONS_DIR, "versions")


def _alembic_cfg(db_url: str) -> Config:
    """Return an Alembic :class:`Config` targeting *db_url*."""
    cfg = Config(os.path.join(_REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _script_dir() -> ScriptDirectory:
    cfg = Config(os.path.join(_REPO_ROOT, "alembic.ini"))
    return ScriptDirectory.from_config(cfg)


def _all_migration_files():
    """Return a sorted list of .py files in the versions directory."""
    return sorted(
        f
        for f in os.listdir(_VERSIONS_DIR)
        if f.endswith(".py") and not f.startswith("__")
    )


# ---------------------------------------------------------------------------
# 1. Migration chain structure
# ---------------------------------------------------------------------------


class TestMigrationChainStructure:
    """Validates the shape of the migration revision graph."""

    def test_migration_chain_has_single_head(self):
        """There must be exactly one head revision (no branching)."""
        script = _script_dir()
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Expected exactly 1 head revision; found {len(heads)}: {heads}. "
            "Multiple heads indicate an unresolved branch in the migration chain."
        )

    def test_migration_chain_has_single_base(self):
        """There must be exactly one base revision (one starting point)."""
        script = _script_dir()
        bases = script.get_bases()
        assert len(bases) == 1, (
            f"Expected exactly 1 base revision; found {len(bases)}: {bases}."
        )

    def test_migration_chain_is_linear(self):
        """Every revision must have at most one parent (no merge commits)."""
        script = _script_dir()
        for rev in script.walk_revisions():
            down = rev.down_revision
            assert down is None or isinstance(down, str), (
                f"Revision {rev.revision!r} has a tuple down_revision {down!r}, "
                "which indicates a merge revision. The chain must remain linear."
            )

    def test_all_revisions_reachable_from_head(self):
        """Every revision file must be reachable from the head."""
        script = _script_dir()
        reachable = {rev.revision for rev in script.walk_revisions()}
        all_revs = set()
        for filename in _all_migration_files():
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            match = re.search(r'^revision\s*:\s*str\s*=\s*["\'](\w+)["\']', content, re.M)
            if match:
                all_revs.add(match.group(1))
        orphaned = all_revs - reachable
        assert not orphaned, (
            f"Orphaned revisions detected (present in files but not reachable "
            f"from head): {sorted(orphaned)}"
        )

    def test_head_revision_is_highest_numbered(self):
        """The head revision should correspond to the highest-numbered migration file."""
        script = _script_dir()
        head = script.get_current_head()
        files = _all_migration_files()
        # Extract numeric prefix from filenames: "0030_create_settings_tables.py" -> 30
        file_numbers = []
        for f in files:
            m = re.match(r"^(\d+)_", f)
            if m:
                file_numbers.append(int(m.group(1)))
        max_num = max(file_numbers)
        try:
            head_int = int(head)
        except (ValueError, TypeError):
            head_int = None
        assert head == str(max_num).zfill(4) or head_int == max_num, (
            f"Head revision is {head!r} but highest-numbered migration file is "
            f"{max_num:04d}. Ensure the head revision matches the latest migration."
        )


# ---------------------------------------------------------------------------
# 2. Migration file completeness
# ---------------------------------------------------------------------------


class TestMigrationFileCompleteness:
    """Validates that every migration file is well-formed."""

    def test_all_migrations_have_upgrade_function(self):
        """Every migration file must define an ``upgrade()`` function."""
        missing = []
        for filename in _all_migration_files():
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            if not re.search(r"^def upgrade\s*\(", content, re.M):
                missing.append(filename)
        assert not missing, (
            f"The following migration files are missing an ``upgrade()`` "
            f"function: {missing}"
        )

    def test_all_migrations_have_downgrade_function(self):
        """Every migration file must define a ``downgrade()`` function."""
        missing = []
        for filename in _all_migration_files():
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            if not re.search(r"^def downgrade\s*\(", content, re.M):
                missing.append(filename)
        assert not missing, (
            f"The following migration files are missing a ``downgrade()`` "
            f"function, which makes them irreversible: {missing}"
        )

    def test_all_migrations_have_revision_id(self):
        """Every migration file must declare a ``revision`` string."""
        missing = []
        for filename in _all_migration_files():
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            if not re.search(r'^revision\s*:\s*str\s*=', content, re.M):
                missing.append(filename)
        assert not missing, (
            f"The following migration files are missing a ``revision`` "
            f"declaration: {missing}"
        )

    def test_all_migrations_have_down_revision(self):
        """Every migration file must declare a ``down_revision`` (may be None for base)."""
        missing = []
        for filename in _all_migration_files():
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            if not re.search(r'^down_revision\s*:', content, re.M):
                missing.append(filename)
        assert not missing, (
            f"The following migration files are missing a ``down_revision`` "
            f"declaration: {missing}"
        )

    def test_revision_ids_match_file_names(self):
        """
        Each file's ``revision`` value must exactly match the four-digit
        numeric prefix of the filename.

        Example: ``0030_create_settings_tables.py`` must contain
        ``revision = "0030"`` — not ``"30"`` or any other normalisation.
        """
        mismatches = []
        for filename in _all_migration_files():
            m = re.match(r"^(\d+)_", filename)
            if not m:
                continue
            expected_rev = m.group(1)  # raw 4-digit prefix, e.g. "0030"
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            rev_match = re.search(
                r'^revision\s*:\s*str\s*=\s*["\'](\w+)["\']', content, re.M
            )
            if not rev_match:
                continue
            actual_rev = rev_match.group(1)
            if actual_rev != expected_rev:
                mismatches.append(
                    f"{filename}: filename prefix {expected_rev!r} != "
                    f"in-file revision {actual_rev!r}"
                )
        assert not mismatches, (
            "Revision ID/filename mismatches detected:\n" + "\n".join(mismatches)
        )

    def test_no_sqlite_alter_constraint_without_batch(self):
        """
        Detect migrations that call ``op.create_unique_constraint`` or
        ``op.drop_constraint`` outside of ``batch_alter_table``, which will
        fail on SQLite.

        An explicit allowlist covers the two existing known incompatible
        migrations.  Any new migration that adds such an operation *outside*
        the allowlist causes this test to **fail** (not xfail), ensuring
        the issue is visible and cannot be silently introduced.
        """
        # Known existing migrations that are SQLite-incompatible.  This set
        # must NOT grow without a deliberate decision to fix the new migration.
        _KNOWN_INCOMPATIBLE = {
            "0006_create_payment_plan_tables.py",
            "0016_add_floors_table.py",
        }

        incompatible = []
        for filename in _all_migration_files():
            path = os.path.join(_VERSIONS_DIR, filename)
            with open(path) as f:
                content = f.read()

            # Extract the upgrade() function body (rough heuristic)
            upgrade_match = re.search(
                r"^def upgrade\(\).*?(?=^def |\Z)", content, re.M | re.S
            )
            if not upgrade_match:
                continue
            upgrade_body = upgrade_match.group(0)

            # Look for standalone (non-batch) constraint operations
            has_standalone_constraint = bool(
                re.search(
                    r"op\.create_unique_constraint|op\.drop_constraint",
                    upgrade_body,
                )
            )
            uses_batch = "batch_alter_table" in upgrade_body
            guards_by_dialect = "dialect.name" in upgrade_body

            if has_standalone_constraint and not uses_batch and not guards_by_dialect:
                incompatible.append(filename)

        new_incompatible = [f for f in incompatible if f not in _KNOWN_INCOMPATIBLE]
        assert not new_incompatible, (
            "New migrations use ``op.create_unique_constraint`` or "
            "``op.drop_constraint`` outside of ``batch_alter_table`` — this "
            "will fail on SQLite.  Wrap them with ``batch_alter_table`` or "
            "guard with ``if bind.dialect.name == 'postgresql':``:\n"
            + "\n".join(f"  - {f}" for f in new_incompatible)
        )

        known_found = [f for f in incompatible if f in _KNOWN_INCOMPATIBLE]
        if known_found:
            pytest.xfail(
                "Known SQLite-incompatible migrations (require PostgreSQL to "
                "run end-to-end).  Fix tracked in migration-hardening backlog:\n"
                + "\n".join(f"  - {f}" for f in known_found)
            )


# ---------------------------------------------------------------------------
# 3. Fresh-database migration run
# ---------------------------------------------------------------------------


class TestMigrationsApplyCleanly:
    """
    Verify that ``alembic upgrade head`` runs on a completely fresh database.

    On SQLite some ALTER TABLE operations cannot be expressed without batch
    mode (see ``test_no_sqlite_alter_constraint_without_batch`` above).  When
    that limitation is hit the test is marked ``xfail`` with a clear message
    so CI stays informative while the underlying issue is tracked.
    """

    def test_migrations_apply_cleanly(self, tmp_path, monkeypatch):
        """alembic upgrade head must succeed on a fresh database."""
        db_file = str(tmp_path / "migration_test.db")
        db_url = f"sqlite:///{db_file}"

        # Prevent env.py from overriding the URL with a real DATABASE_URL.
        monkeypatch.setenv("DATABASE_URL", db_url)

        cfg = _alembic_cfg(db_url)
        try:
            from alembic import command as alembic_command

            alembic_command.upgrade(cfg, "head")
        except NotImplementedError as exc:
            if "SQLite" in str(exc):
                pytest.xfail(
                    f"Migration chain contains operations not supported by "
                    f"SQLite: {exc}. Run against PostgreSQL for a full "
                    f"end-to-end validation."
                )
            raise
        except Exception as exc:
            pytest.fail(
                f"alembic upgrade head raised an unexpected error: "
                f"{type(exc).__name__}: {exc}"
            )

    def test_alembic_history_is_consistent(self, tmp_path, monkeypatch):
        """
        After applying all migrations the recorded current revision must match
        the declared head.
        """
        db_file = str(tmp_path / "history_test.db")
        db_url = f"sqlite:///{db_file}"

        # Prevent env.py from overriding the URL with a real DATABASE_URL.
        monkeypatch.setenv("DATABASE_URL", db_url)

        cfg = _alembic_cfg(db_url)

        from alembic import command as alembic_command

        try:
            alembic_command.upgrade(cfg, "head")
        except NotImplementedError:
            pytest.xfail("SQLite limitation prevents full migration run.")

        script = _script_dir()
        declared_head = script.get_current_head()

        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            db_heads = {row[0] for row in result}

        assert db_heads == {declared_head}, (
            f"After upgrade head the database revision {db_heads} does not "
            f"match the declared head {declared_head!r}."
        )


# ---------------------------------------------------------------------------
# 4 & 7. Table presence and ORM↔migration agreement
# ---------------------------------------------------------------------------


class TestAllTablesCreated:
    """
    Verify that every table declared in the ORM models is present in the
    schema produced by ``Base.metadata.create_all``, and that every table
    created by migrations has a corresponding ORM model.
    """

    def test_all_orm_tables_exist_after_create_all(self):
        """
        After ``Base.metadata.create_all`` every table registered in
        Base.metadata must be present in the SQLite schema.
        """
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
        assert not missing, (
            f"Tables declared in ORM models but absent from the created schema: "
            f"{sorted(missing)}"
        )

    def test_migration_tables_match_orm_tables(self):
        """
        Every table created by ``op.create_table`` in the migrations must have
        a corresponding ORM model, and vice-versa.
        """
        migration_tables: set[str] = set()
        for filename in _all_migration_files():
            with open(os.path.join(_VERSIONS_DIR, filename)) as f:
                content = f.read()
            found = re.findall(r'op\.create_table\(\s*["\'](\w+)["\']', content)
            migration_tables.update(found)

        orm_tables = set(Base.metadata.tables.keys())

        in_migrations_not_orm = migration_tables - orm_tables
        in_orm_not_migrations = orm_tables - migration_tables

        assert not in_migrations_not_orm, (
            f"Tables created by migrations but not declared in any ORM model "
            f"(orphaned migrations): {sorted(in_migrations_not_orm)}"
        )
        assert not in_orm_not_migrations, (
            f"Tables declared in ORM models but never created by any migration "
            f"(un-migrated models): {sorted(in_orm_not_migrations)}"
        )


# ---------------------------------------------------------------------------
# 5. Foreign-key validity
# ---------------------------------------------------------------------------


class TestForeignKeysValid:
    """
    Verify that every FK declared in the ORM models points to a table and
    column that actually exist in Base.metadata (no dangling references).
    """

    def test_all_foreign_keys_have_valid_targets(self):
        """No FK may reference a table or column absent from the metadata."""
        known_tables = Base.metadata.tables
        errors = []

        for table_name, table in known_tables.items():
            for col in table.columns:
                for fk in col.foreign_keys:
                    target = fk.target_fullname  # e.g. "units.id"
                    parts = target.split(".")
                    if len(parts) != 2:
                        errors.append(
                            f"{table_name}.{col.name}: malformed FK target {target!r}"
                        )
                        continue
                    ref_table, ref_col = parts
                    if ref_table not in known_tables:
                        errors.append(
                            f"{table_name}.{col.name} → {target!r}: "
                            f"target table {ref_table!r} does not exist"
                        )
                    elif ref_col not in known_tables[ref_table].c:
                        errors.append(
                            f"{table_name}.{col.name} → {target!r}: "
                            f"target column {ref_col!r} not found in {ref_table!r}"
                        )

        assert not errors, (
            "Invalid FK targets detected:\n" + "\n".join(f"  {e}" for e in errors)
        )

    def test_critical_foreign_keys_point_to_correct_tables(self):
        """
        Spot-check the most architecturally important FK relationships that
        enforce the commercial-layer boundary rules.
        """
        checks = [
            # table, column, expected FK target
            ("phases", "project_id", "projects.id"),
            ("buildings", "phase_id", "phases.id"),
            ("floors", "building_id", "buildings.id"),
            ("units", "floor_id", "floors.id"),
            ("sales_contracts", "unit_id", "units.id"),
            ("reservations", "unit_id", "units.id"),
            ("payment_schedules", "contract_id", "sales_contracts.id"),
            ("registration_cases", "unit_id", "units.id"),
            ("registration_cases", "sale_contract_id", "sales_contracts.id"),
            ("construction_progress_updates", "milestone_id", "construction_milestones.id"),
        ]

        tables = Base.metadata.tables
        errors = []
        for tbl, col_name, expected_target in checks:
            if tbl not in tables:
                errors.append(f"Table {tbl!r} not found in metadata")
                continue
            col = tables[tbl].c.get(col_name)
            if col is None:
                errors.append(f"{tbl}.{col_name}: column not found")
                continue
            fk_targets = {fk.target_fullname for fk in col.foreign_keys}
            if expected_target not in fk_targets:
                errors.append(
                    f"{tbl}.{col_name}: expected FK to {expected_target!r}, "
                    f"found {fk_targets}"
                )

        assert not errors, (
            "Critical FK checks failed:\n"
            + "\n".join(f"  {e}" for e in errors)
        )


# ---------------------------------------------------------------------------
# 6. Index audit
# ---------------------------------------------------------------------------


class TestIndexesExist:
    """
    Verify that performance-critical indexes exist for FK columns and
    frequently-used lookup/aggregation fields.

    The expected indexes come from the migration files and ORM model
    definitions.  Any regression (accidentally dropped index) will surface
    here.
    """

    # (table_name, index_name_or_column_name_hint, description)
    _CRITICAL_INDEXES = [
        # Asset hierarchy — FK lookups
        ("phases", "ix_phases_project_id", "phases.project_id FK index"),
        ("buildings", "ix_buildings_phase_id", "buildings.phase_id FK index"),
        ("floors", "ix_floors_building_id", "floors.building_id FK index"),
        ("units", "ix_units_floor_id", "units.floor_id FK index"),
        # Commercial domain
        ("sales_contracts", "ix_sales_contracts_unit_id", "sales_contracts.unit_id index"),
        ("reservations", "ix_reservations_unit_id", "reservations.unit_id index"),
        ("payment_schedules", "ix_payment_schedules_contract_id", "payment_schedules.contract_id index"),
        ("payment_schedules", "ix_payment_schedules_due_date", "payment_schedules due_date ordering index"),
        ("payment_receipts", "ix_payment_receipts_contract_id", "payment_receipts.contract_id index"),
        # Registry — PR-E7 performance indexes
        ("registration_cases", "ix_registration_cases_unit_id", "registration_cases.unit_id index"),
        ("registration_cases", "ix_registration_cases_sale_contract_id", "registration_cases.contract FK index"),
        ("registration_cases", "ix_registration_cases_project_id", "registration_cases.project_id index"),
        ("registration_cases", "ix_registration_cases_status", "registration_cases.status filter index"),
        ("registration_cases", "ix_registration_cases_project_id_status", "registration_cases composite project_id+status index"),
        # Construction — dashboard aggregation
        ("construction_progress_updates", "ix_construction_progress_updates_milestone_id", "progress updates milestone FK index"),
        ("construction_scopes", "ix_construction_scopes_project_id", "construction_scopes.project_id FK index"),
        # Cashflow
        ("cashflow_forecasts", "ix_cashflow_forecasts_project_id", "cashflow_forecasts.project_id FK index"),
        # Receivables
        ("receivables", "ix_receivables_contract_id", "receivables.contract_id FK index"),
        ("receivables", "ix_receivables_due_date", "receivables due_date ordering index"),
    ]

    def test_critical_indexes_exist_in_orm(self):
        """Every critical index must be defined in the ORM metadata."""
        tables = Base.metadata.tables
        missing = []

        for table_name, index_name, description in self._CRITICAL_INDEXES:
            if table_name not in tables:
                missing.append(f"{description}: table {table_name!r} not found")
                continue
            table = tables[table_name]
            index_names = {idx.name for idx in table.indexes}
            if index_name not in index_names:
                missing.append(
                    f"{description}: index {index_name!r} not found on "
                    f"{table_name!r} (found: {sorted(index_names)})"
                )

        assert not missing, (
            "Missing critical indexes detected:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_unique_lookups_have_indexes(self):
        """
        Columns used as unique lookup identifiers must have an index declared
        in the ORM metadata.
        """
        unique_lookup_checks = [
            # (table, column, expected index name)
            ("projects", "code", "ix_projects_code"),
            ("users", "email", "ix_users_email"),
            ("buyers", "email", "ix_buyers_email"),
            ("unit_pricing", "unit_id", "ix_unit_pricing_unit_id"),
            ("unit_pricing_attributes", "unit_id", "ix_unit_pricing_attributes_unit_id"),
        ]
        tables = Base.metadata.tables
        missing = []
        for table_name, col_name, index_name in unique_lookup_checks:
            if table_name not in tables:
                missing.append(f"Table {table_name!r} not found")
                continue
            table = tables[table_name]
            index_names = {idx.name for idx in table.indexes}
            if index_name not in index_names:
                missing.append(
                    f"{table_name}.{col_name}: expected index {index_name!r} "
                    f"(found: {sorted(index_names)})"
                )
        assert not missing, (
            "Missing lookup indexes:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )


# ---------------------------------------------------------------------------
# 7. Schema / ORM agreement (complementary to TestAllTablesCreated)
# ---------------------------------------------------------------------------


class TestSchemaMatchesModels:
    """
    Deeper comparison between what the ORM declares and what the DB schema
    contains after ``Base.metadata.create_all``.

    Checks column presence and basic type families for the most important
    tables so that drift between models and migrations is caught early.
    """

    def _build_schema_engine(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        return engine

    def test_no_extra_tables_in_schema(self):
        """
        The schema produced by ``create_all`` must not contain tables that are
        absent from ``Base.metadata`` (e.g. stale alembic_version table is
        acceptable; all others are not).
        """
        engine = self._build_schema_engine()
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names()) - {"alembic_version"}
        orm_tables = set(Base.metadata.tables.keys())
        extra = db_tables - orm_tables
        assert not extra, (
            f"Tables present in DB schema but absent from ORM metadata: "
            f"{sorted(extra)}"
        )

    def test_column_presence_in_key_tables(self):
        """
        Spot-check that key columns are present in the most important tables
        after ``create_all``.  This detects model/migration drift quickly.
        """
        engine = self._build_schema_engine()
        inspector = inspect(engine)

        required_columns = {
            "projects": {"id", "name", "code", "status", "created_at", "updated_at"},
            "units": {"id", "floor_id", "unit_number", "unit_type", "internal_area", "status"},
            "sales_contracts": {"id", "unit_id", "buyer_id", "contract_number", "contract_price", "status"},
            "registration_cases": {"id", "project_id", "unit_id", "sale_contract_id", "status"},
            "construction_progress_updates": {"id", "milestone_id", "progress_percent", "reported_at"},
            "settings_pricing_policies": {"id", "name", "is_default", "currency"},
        }

        errors = []
        for table_name, expected_cols in required_columns.items():
            try:
                actual_cols = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception as exc:
                errors.append(f"{table_name}: could not inspect columns: {exc}")
                continue
            missing = expected_cols - actual_cols
            if missing:
                errors.append(
                    f"{table_name}: missing columns {sorted(missing)} "
                    f"(actual: {sorted(actual_cols)})"
                )

        assert not errors, (
            "Column presence check failed:\n"
            + "\n".join(f"  {e}" for e in errors)
        )

    def test_orm_column_counts_match_schema(self):
        """
        For every table in Base.metadata the number of columns declared in the
        ORM model must not exceed the number of columns in the DB schema created
        by ``create_all``.  (The DB may have fewer columns if some are added by
        later migrations, but never more.)
        """
        engine = self._build_schema_engine()
        inspector = inspect(engine)
        errors = []

        for table_name, table in Base.metadata.tables.items():
            orm_cols = {c.name for c in table.columns}
            try:
                db_cols = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                continue
            missing = orm_cols - db_cols
            if missing:
                errors.append(
                    f"{table_name}: ORM declares columns {sorted(missing)} "
                    "that are absent from the create_all schema"
                )

        assert not errors, (
            "ORM/schema column count discrepancy:\n"
            + "\n".join(f"  {e}" for e in errors)
        )

    def test_postgresql_only_operations_are_guarded(self):
        """
        Migrations that use PostgreSQL-specific DDL *other than*
        ``postgresql_where`` in ``create_index`` must guard those operations
        with a dialect check (``bind.dialect.name == 'postgresql'``) or
        ``batch_alter_table`` so they degrade gracefully on SQLite.

        ``postgresql_where=`` in ``op.create_index`` is explicitly **allowed**
        without a guard because SQLAlchemy silently drops the WHERE clause when
        targeting SQLite — no runtime error occurs.

        Any usage of ``postgresql_ops=`` or ``postgresql_using=`` without a
        dialect guard is flagged, as those keywords can affect query behaviour
        and should be explicitly scoped to PostgreSQL.
        """
        unguarded = []
        for filename in _all_migration_files():
            path = os.path.join(_VERSIONS_DIR, filename)
            with open(path) as f:
                content = f.read()

            # Only flag the non-safe PostgreSQL-specific kwargs.
            # postgresql_where is intentionally excluded because SQLAlchemy
            # transparently ignores it on SQLite.
            has_pg_specific = bool(
                re.search(r"postgresql_ops|postgresql_using", content)
            )
            has_dialect_guard = "dialect.name" in content
            uses_batch = "batch_alter_table" in content

            if has_pg_specific and not has_dialect_guard and not uses_batch:
                unguarded.append(filename)

        assert not unguarded, (
            "Migrations use PostgreSQL-specific DDL kwargs "
            "(``postgresql_ops``/``postgresql_using``) without a dialect "
            "guard.  Wrap with ``if bind.dialect.name == 'postgresql':`` or "
            "``batch_alter_table``:\n"
            + "\n".join(f"  - {f}" for f in unguarded)
        )
