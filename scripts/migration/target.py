"""The half of preflight that has to look at the system being migrated into.

The source-side half asks whether the bundle is the bundle somebody validated.
This half asks the questions only the target can answer, and every one of them
has a night-of failure behind it:

* **Is the database the one this code expects?** A batch applied against a
  schema older or newer than the code applying it writes to columns whose
  meaning it has guessed. The comparison is against *this checkout's* migration
  head, because this checkout is what holds the assumptions.
* **Does the project exist?** A cutover resolves a project and never creates
  one. A cutover that can bring a project into existence can bring the wrong one.
* **Are the declared currencies configured?** The manifest declares which
  currencies the batch may contain. A code the system does not have is a
  refusal, never a creation and never a conversion — there is no FX here and a
  cutover is not the place to invent one.
* **Has this batch already been applied?** The question the whole of
  ``batch.py`` exists to answer, asked before anything is written rather than
  after.

Every function here reads. Nothing opens a write transaction, takes a lock or
commits, because an operator asking "did last night's batch land?" must not be
able to change anything by asking. The lock belongs to ``batch.claim``, at the
moment something is actually at stake.

If the database is unreachable the remaining checks are not attempted and not
reported as though they were. A report that lists four passes it never made is
worse than one that lists a single failure, because the first is believed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_engine, get_session_factory
from app.modules.settings.models import Currency
from scripts.migration.batch import BatchRefused, claim_of, resolve_project

if TYPE_CHECKING:  # pragma: no cover - typing only
    from scripts.migration.manifest import Manifest

#: The repository root, from this file rather than from the working directory:
#: an operator running the CLI from somewhere else must still get this
#: checkout's migration history and not whatever ``alembic.ini`` is nearest.
ROOT = Path(__file__).resolve().parents[2]


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    """One row of the report, in the shape the source-side half already uses."""
    return {"check": name, "result": "PASS" if ok else "FAIL", "detail": detail}


def expected_head() -> str:
    """The migration head this checkout's code is written against."""
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "app" / "db" / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:  # pragma: no cover - a history with no revisions
        raise RuntimeError("this checkout has no migration history to compare against.")
    return head


def applied_head() -> str | None:
    """The revision the database is actually at, or ``None`` if it has none."""
    with get_engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def inspect(manifest: Manifest) -> list[dict[str, Any]]:
    """Every target-side check, as report rows. Reads only.

    Ordered so the first failure is the most fundamental one: an unreachable
    database makes the rest unanswerable, and they are then left unasked rather
    than reported as passes nobody made.
    """
    try:
        current = applied_head()
    except SQLAlchemyError as error:
        return [
            _check(
                "database_reachable",
                False,
                f"{type(error).__name__}: {error}. The remaining target checks were not "
                "attempted, so nothing below this line has been established.",
            )
        ]

    checks = [_check("database_reachable", True, "The target answered.")]

    wanted = expected_head()
    checks.append(
        _check(
            "schema_at_expected_head",
            current == wanted,
            f"The database is at {current or 'no revision'} and this code expects {wanted}."
            + (
                ""
                if current == wanted
                else " Applying against a schema this code was not written for writes to columns"
                " whose meaning it has guessed."
            ),
        )
    )

    session = get_session_factory()()
    try:
        try:
            project = resolve_project(session, manifest.project_code)
            checks.append(
                _check(
                    "project_known",
                    True,
                    f"{manifest.project_code} resolves to project {project.id}.",
                )
            )
        except BatchRefused as error:
            checks.append(_check("project_known", False, str(error)))

        configured = set(
            session.scalars(
                select(Currency.code).where(Currency.code.in_(manifest.expected_currencies))
            )
        )
        missing = sorted(set(manifest.expected_currencies) - configured)
        checks.append(
            _check(
                "currencies_configured",
                not missing,
                f"All {len(manifest.expected_currencies)} declared currencies are configured."
                if not missing
                else f"Not configured: {', '.join(missing)}. A currency is set up in the "
                "application before a batch runs; a cutover never creates one and never "
                "converts into one.",
            )
        )

        existing = claim_of(session, manifest.batch_id)
        checks.append(
            _check(
                "batch_not_applied",
                existing is None,
                "No claim exists for this batch."
                if existing is None
                else f"Batch {manifest.batch_id} was applied at "
                f"{existing.occurred_at.isoformat()}. A batch is applied once.",
            )
        )
    finally:
        # Read-only throughout, so there is nothing to commit and the rollback
        # is what releases the connection's snapshot rather than an undo.
        session.rollback()
        session.close()

    return checks
