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
