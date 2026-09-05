"""Guards on the cutover package's place in the fast test selector.

Two things are being protected here and they pull in opposite directions.

The cutover package sits under ``scripts/``, where the selector's default is to
run the entire suite. That default exists for a good reason — ``render-build.sh``
and ``render-start.sh`` live there and start the deployed application — and this
package is named out of it deliberately, because it is stdlib-only tooling that
nothing in ``app/`` imports and that a running application never reaches.

The danger in carving out that exception is that it stops being true. The day
the cutover writers start calling domain services, a change in one of those
domains can break the cutover and the fast run would not notice. So the
exception is paired with a guard: every application module the package imports
must have a path to ``cutover`` in the dependency map before the narrow run is
allowed to stay narrow.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_backend_tests as selector  # noqa: E402

CUTOVER = selector.CUTOVER_DOMAIN
PACKAGE = ROOT / "scripts" / "migration"


def reaches(start: str, target: str) -> bool:
    """Whether a change in ``start`` runs ``target``'s tests, transitively."""
    seen: set[str] = set()
    queue = deque(selector.DOWNSTREAM.get(start, ()))
    while queue:
        domain = queue.popleft()
        if domain == target:
            return True
        if domain in seen:
            continue
        seen.add(domain)
        queue.extend(selector.DOWNSTREAM.get(domain, ()))
    return False


def chosen(*paths: str) -> selector.Selection:
    return selector.select(
        list(paths), sorted(str(p.relative_to(ROOT)) for p in ROOT.glob("tests/**/test_*.py"))
    )


# --------------------------------------------------------------------------- #
# The exception
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        "scripts/migration/__init__.py",
        "scripts/migration/manifest.py",
        "scripts/migration/reporting.py",
    ],
)
def test_a_cutover_change_runs_the_cutover_tests_and_not_the_world(path: str) -> None:
    result = chosen(path)
    assert result.full is False
    assert result.domains == [CUTOVER]


def test_the_cutover_tests_are_claimed_by_the_cutover_domain() -> None:
    """Named ``test_cutover_*`` on purpose.

    ``test_migration_*`` is already taken: those ten files are Alembic
    schema-revision tests and each belongs to the domain it revises. A
    ``migration`` domain here would have claimed all ten and quietly narrowed
    every one of those fast runs.
    """
    assert selector.DOMAIN_TEST_PREFIXES[CUTOVER] == ("cutover",)
    for domain, prefixes in selector.DOMAIN_TEST_PREFIXES.items():
        if domain == CUTOVER:
            continue
        assert "cutover" not in prefixes, domain


# --------------------------------------------------------------------------- #
# ...which must not widen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("path", ["scripts/render-start.sh", "scripts/render-build.sh"])
def test_a_deployment_script_still_runs_everything(path: str) -> None:
    """The reason for the ``scripts/`` fallback is unchanged and still applies."""
    assert chosen(path).full is True


def test_the_exception_is_one_named_package_not_a_pattern() -> None:
    assert selector.CUTOVER_PACKAGE == "scripts/migration/"
    assert chosen("scripts/migration_helper.py").full is True


# --------------------------------------------------------------------------- #
# The self-policing part
# --------------------------------------------------------------------------- #


def imported_domains() -> set[str]:
    """Which application domains the cutover package imports today."""
    found: set[str] = set()
    for source in sorted(PACKAGE.glob("**/*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            for name in names:
                parts = name.split(".")
                if len(parts) >= 3 and parts[0] == "app" and parts[1] == "modules":
                    found.add(parts[2])
    return found


def test_every_domain_the_cutover_imports_can_reach_it() -> None:
    """The exception stays honest as the package grows.

    Today the cutover is stdlib-only and this passes with nothing to check. The
    first importer that calls a domain service makes it real: without an edge,
    a change in that domain would leave the cutover untested on every fast run,
    which is the failure the whole selector exists to prevent.
    """
    for domain in sorted(imported_domains()):
        assert domain in selector.DOMAIN_TEST_PREFIXES, (
            f"scripts/migration imports app.modules.{domain}, which no domain claims."
        )
        assert reaches(domain, CUTOVER), (
            f"scripts/migration imports app.modules.{domain}, so a change there can break "
            f"the cutover — add a DOWNSTREAM edge reaching {CUTOVER!r} before this can pass."
        )


def test_only_the_cutover_family_reads_the_cutover_fixtures() -> None:
    """The honesty condition on the second selector exception.

    ``tests/fixtures/cutover/`` is named out of the "anything under tests/ that
    is not a test is shared support" fallback, so editing a row of fictional
    data costs a targeted run rather than two and a half hours. That is only
    safe while the fixtures are read by the cutover family alone: the moment
    another domain's test reads them, a change to a CSV could break it and the
    fast run would not have covered it.

    The same shape as the guard above, for the same reason. An exception nobody
    re-checks stops being an exception and becomes a hole.
    """
    readers = sorted(
        path.name
        for path in ROOT.glob("tests/**/*.py")
        if "tests/fixtures/cutover" in path.read_text(encoding="utf-8")
    )
    assert readers, "nothing reads the fixtures — has the carve-out outlived its bundle?"
    strangers = [name for name in readers if not name.startswith("test_cutover_")]
    assert not strangers, (
        f"{strangers} read tests/fixtures/cutover/, which a cutover-only fast run "
        "would not cover — either move the fixture or drop the selector exception."
    )


def test_the_cutover_feeds_nothing_back_into_the_platform() -> None:
    """Edges point into the cutover, never out of it.

    An edge out would say a cutover change can break a domain, and it cannot:
    nothing in ``app/`` imports this package, and a running application never
    reaches it.
    """
    assert selector.DOWNSTREAM[CUTOVER] == ()
    assert not any(
        source
        for source in ROOT.glob("app/**/*.py")
        if "scripts.migration" in source.read_text(encoding="utf-8")
    )


# --------------------------------------------------------------------------- #
# An operational domain is not a schema domain
# --------------------------------------------------------------------------- #


def test_an_alembic_revision_cannot_be_claimed_by_the_cutover_domain() -> None:
    """The regression this file's own change introduced, and its fix.

    ``domain_of_migration`` decides whose schema a revision reshapes by matching
    the revision's file name against the domain map. Adding ``cutover`` to that
    map made ``0012_legacy_cutover.py`` claimable by tooling that owns no
    tables — and PR-MVP-11 may well add a revision with exactly that name, since
    the legacy commercial provenance seam is on its way. It would have run three
    text-reading tests in place of the full suite an unrecognised schema change
    deserves.
    """
    assert selector.domain_of_migration("app/db/migrations/versions/0012_legacy_cutover.py") is None
    assert chosen("app/db/migrations/versions/0012_legacy_cutover.py").full is True


def test_schema_domains_still_claim_their_own_revisions() -> None:
    """The exclusion is one named domain, not a hole in the mechanism."""
    assert selector.domain_of_migration("app/db/migrations/versions/0006_payment_plans.py") == (
        "payment_plans"
    )
    assert selector.domain_of_migration("app/db/migrations/versions/0003_inventory.py") == (
        "inventory"
    )


def test_only_operational_domains_are_excluded_from_schema_inference() -> None:
    assert frozenset({CUTOVER}) == selector.NON_SCHEMA_DOMAINS
    assert CUTOVER in selector.DOMAIN_TEST_PREFIXES
