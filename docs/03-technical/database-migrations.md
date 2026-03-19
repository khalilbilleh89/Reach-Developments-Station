# Database Migrations

## Overview

Reach Developments Station uses [Alembic](https://alembic.sqlalchemy.org/) to manage
all database schema changes. Every structural change to the database — creating tables,
adding columns, altering constraints — must go through a migration file. Direct DDL
against the database is prohibited.

The migration chain currently contains **29 revisions** (0001 – 0030, with 0015 reserved).
All revisions form a single linear chain from base `0001` to head `0030`.

---

## Migration Workflow

### Generating a new migration

1. Make the change in the relevant SQLAlchemy model (`app/modules/<domain>/models.py`).
2. From the project root, generate a migration file:

   ```bash
   alembic revision --autogenerate -m "describe your change"
   ```

3. **Always review** the generated file before committing:
   - Confirm the `upgrade()` body matches your intent.
   - Write a matching `downgrade()` that fully reverses the upgrade.
   - Add a numbered prefix to the filename matching the sequence
     (e.g. `0031_add_some_column.py`).
   - Ensure the `revision` and `down_revision` fields are correct.

4. Rename the file to follow the project convention:

   ```
   <NNNN>_<snake_case_description>.py
   ```

### Applying migrations

```bash
# Upgrade to the latest revision
alembic upgrade head

# Upgrade to a specific revision
alembic upgrade 0025

# Show current revision in the database
alembic current

# Show full migration history
alembic history --verbose
```

### Rolling back migrations

```bash
# Roll back one revision
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade 0024

# Roll back everything (back to an empty database)
alembic downgrade base
```

> **Warning**: Downgrading in production requires careful planning. Always take a
> database backup before running a downgrade.

---

## Environment Configuration

Alembic reads the database URL from the `DATABASE_URL` environment variable. If the
variable is not set it falls back to the placeholder URL in `alembic.ini` (which will
not work and is intentionally invalid for safety).

```bash
# Development / CI (SQLite)
DATABASE_URL="sqlite:///dev.db" alembic upgrade head

# Production (PostgreSQL)
DATABASE_URL="postgresql+psycopg2://user:pass@host/dbname" alembic upgrade head
```

---

## Validating Migrations

### Automated test suite

Migration integrity is enforced by the architecture test suite:

```bash
pytest tests/architecture/test_migration_integrity.py -v
```

The test file covers:

| Test class | What it validates |
|---|---|
| `TestMigrationChainStructure` | Single head/base, linear chain, all revisions reachable |
| `TestMigrationFileCompleteness` | All files declare `upgrade()`, `downgrade()`, `revision`, `down_revision` |
| `TestMigrationsApplyCleanly` | `alembic upgrade head` succeeds on a fresh DB |
| `TestAllTablesCreated` | ORM tables created by `Base.metadata.create_all`, migrations↔ORM parity |
| `TestForeignKeysValid` | No dangling FK targets; critical FK topology enforced |
| `TestIndexesExist` | All performance-critical indexes present |
| `TestSchemaMatchesModels` | Column presence, no extra tables, ORM/DB column parity |

### Local helper script

A standalone script is provided for quick local validation without pytest:

```bash
python scripts/check_migrations.py          # summary output
python scripts/check_migrations.py --verbose # detailed output per check
```

Exit code 0 means all checks passed. Exit code 1 means at least one check failed.

---

## SQLite vs PostgreSQL Compatibility

Tests run against an in-memory **SQLite** database for speed and isolation. The
production database is **PostgreSQL**.

Most migration operations are fully portable. A small number of patterns require care:

### Known SQLite limitations

| Operation | Behaviour on SQLite | Correct approach |
|---|---|---|
| `op.create_unique_constraint` (standalone) | **Fails** — SQLite does not support `ALTER TABLE ADD CONSTRAINT` | Use `batch_alter_table` or inline the constraint in `op.create_table` |
| `op.drop_constraint` (standalone) | **Fails** — same reason | Use `batch_alter_table` |
| `op.alter_column` | **Fails** without batch mode | Use `batch_alter_table` |
| `postgresql_where=` in `create_index` | Silently ignored — SQLite creates a non-partial index | Acceptable; guard with `if bind.dialect.name == 'postgresql':` for precision |

#### Existing known issues

The following migrations use `op.create_unique_constraint` or `op.drop_constraint`
outside of `batch_alter_table` and therefore **cannot run end-to-end on SQLite**:

- `0006_create_payment_plan_tables.py` — `uq_payment_schedules_contract_installment`
- `0016_add_floors_table.py` — multiple unique constraint operations on `floors`

These migrations work correctly on PostgreSQL (production). The migration run tests
are marked `xfail` on SQLite environments to document this limitation without blocking
CI. Fix these by wrapping the operations in `batch_alter_table` in a future
hardening pass (see PR-E2 issues).

### Correct pattern for portable schema changes

**Adding a column** (portable):

```python
def upgrade() -> None:
    op.add_column("my_table", sa.Column("new_col", sa.String(100), nullable=True))

def downgrade() -> None:
    op.drop_column("my_table", "new_col")
```

**Altering a column or constraint** (SQLite-safe via batch mode):

```python
def upgrade() -> None:
    with op.batch_alter_table("my_table") as batch_op:
        batch_op.alter_column("some_col", nullable=True)
        batch_op.create_unique_constraint("uq_my_table_col", ["col_a", "col_b"])

def downgrade() -> None:
    with op.batch_alter_table("my_table") as batch_op:
        batch_op.drop_constraint("uq_my_table_col", type_="unique")
        batch_op.alter_column("some_col", nullable=False)
```

**PostgreSQL-only operation** (guarded by dialect check):

```python
def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_my_table_standalone_code",
            "my_table",
            ["code"],
            unique=True,
            postgresql_where=sa.text("project_id IS NULL"),
        )
```

---

## Migration Naming Convention

```
<NNNN>_<snake_case_description>.py
```

Examples:
- `0001_create_asset_hierarchy.py`
- `0025_harden_land_feasibility_project_independence.py`
- `0030_create_settings_tables.py`

Rules:
- Four-digit zero-padded sequence number
- Underscore separator
- Snake case description, concise but descriptive
- The `revision` field inside the file must match the four-digit prefix (e.g. `"0025"`)

---

## Migration Checklist

Before merging a PR that includes a new migration:

- [ ] File is named correctly (`<NNNN>_<description>.py`)
- [ ] `revision` and `down_revision` fields are correct
- [ ] `upgrade()` function creates/alters exactly what was intended
- [ ] `downgrade()` function fully reverses `upgrade()` (tables dropped in reverse order)
- [ ] No standalone `op.create_unique_constraint` / `op.drop_constraint` / `op.alter_column` — use `batch_alter_table`
- [ ] PostgreSQL-only operations are guarded with `if bind.dialect.name == "postgresql":`
- [ ] Corresponding ORM model changes are in the same PR
- [ ] `pytest tests/architecture/test_migration_integrity.py` passes
- [ ] `python scripts/check_migrations.py` exits with code 0

---

## Troubleshooting

### `alembic current` shows `(head)` but the DB is missing tables

The alembic_version table records which revision was last applied but does not
guarantee the schema matches. Run `alembic upgrade head` to re-apply any missing
steps, or compare with `alembic check` (Alembic 1.9+).

### Migration fails with `NotImplementedError: No support for ALTER of constraints in SQLite`

You are running a migration that uses standalone `op.create_unique_constraint` or
`op.drop_constraint` against a SQLite database. Either:

1. Switch to PostgreSQL for the migration run, or
2. Rewrite the migration using `batch_alter_table` (preferred for portability).

### Multiple heads detected

If `alembic heads` shows more than one revision:

```bash
alembic merge heads -m "merge heads"
```

Review the merge revision carefully and ensure the `downgrade()` correctly reverses
both branches.

### `alembic autogenerate` produces unexpected changes

Alembic compares the ORM models to the **current DB schema**, not to the migration
files. If the DB is out of date relative to the migrations, autogenerate will produce
a diff against the stale schema. Always apply all pending migrations before generating
a new one:

```bash
alembic upgrade head
alembic revision --autogenerate -m "my change"
```
