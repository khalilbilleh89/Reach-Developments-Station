#!/usr/bin/env python3
"""Choose which backend tests a pull request actually needs.

Every push used to run the whole suite. At fifteen hundred tests that turned a
one-line correction into a forty-minute wait, and a wait long enough to walk
away from is a wait that stops being read. So a draft pull request runs the
tests its change can plausibly break, and a pull request marked ready for
review runs all of them. Fast CI is not weaker CI; it answers a narrower
question, and the broad one is still asked before anything merges.

Three ideas, and nothing more:

**A domain owns a family of test files.** The map below is explicit and was
built by reading the actual names in ``tests/``. There is no inference, no
heuristic and no marker to maintain on fifteen hundred tests.

**A change flows downstream, never up.** Sales sits on pricing, so a pricing
change runs sales; a sales change does not re-run pricing. Sales' own tests
already prove its use of pricing's public contract, and the full suite proves
the rest before merge. This asymmetry is where the time is saved.

**Anything unrecognised runs everything.** A new module, a shared fixture, the
core, the access layer — all fall back to the full suite and say so in the log.
The selector fails safe, never open: the cost of a wrong "full" is minutes, and
the cost of a wrong "targeted" is a regression that reaches main.

Run it directly to see what a change would select::

    python scripts/ci_backend_tests.py --changed app/modules/sales/service.py
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# The map
# --------------------------------------------------------------------------- #

#: Tests that run whatever changed: the application boots, its configuration is
#: sound, its migrations are linear, its static export is served, who may call
#: what is still enforced, every write is still audited, and the API's shape has
#: not drifted. A hundred and twenty tests in about eighty seconds — deliberately
#: a backbone and not a second suite.
ALWAYS_RUN = (
    "tests/test_config.py",
    "tests/test_health.py",
    "tests/test_migrations.py",
    "tests/test_static_frontend.py",
    "tests/test_ux_copy.py",
    "tests/modules/test_auth.py",
    "tests/modules/test_authorization.py",
    "tests/modules/test_audit.py",
    "tests/modules/test_strict_requests.py",
    "tests/modules/test_docs_exposure.py",
    # The selector's own tests, including the guard that every test file in the
    # repository is claimed by some domain. Running it every time is what stops
    # this map rotting into a fast suite that quietly covers less each month.
    "tests/test_ci_selector.py",
)

#: Which test files belong to which domain, matched against the file name with
#: its ``test_`` prefix removed. Built by reading ``tests/modules/``; a test
#: that no domain claims is caught by ``unclaimed_test_files`` below, so this
#: map cannot silently rot as files are added.
DOMAIN_TEST_PREFIXES: dict[str, tuple[str, ...]] = {
    "access": ("auth", "authorization", "phase_access", "project_access"),
    "audit": ("audit",),
    "settings": ("settings", "migration_governance"),
    "projects": (
        "projects",
        "project_",
        "parcels",
        "permit",
        "planning",
        "documents",
        "migration_projects",
    ),
    "inventory": (
        "unit",
        "phases",
        "sub_assets",
        "inventory_",
        "custom_field",
        "import_",
        "migration_inventory",
    ),
    "pricing": ("pricing_", "price_versions", "migration_pricing"),
    "sales": ("sales_", "sale_contracts", "reservations", "migration_sales"),
    "payment_plans": ("payment_plan", "migration_payment_plans"),
    "collections": ("collection", "migration_collections"),
    "unit_economics": ("unit_economics", "migration_unit_economics"),
    "construction": ("construction", "migration_construction"),
}

#: What each domain feeds **directly**. Read strictly downstream: a change here
#: can break these, so their tests run too. The reverse does not hold, which is
#: the whole point — collections leaning on sales does not make a collections
#: edit a reason to re-prove sales.
#:
#: These are edges, not reachability. :func:`closure` walks them, so adding a
#: domain means adding one edge and nothing else. Spelling out every descendant
#: here instead would mean that giving payment plans a downstream neighbour
#: required editing pricing, inventory, projects and settings too — and the
#: first person to forget one would get a targeted run that silently skipped
#: the new domain.
#:
#: ``projects`` and ``settings`` sit above the business stack rather than in it:
#: every record is project-scoped and every project is configured from a country
#: pack, so a change to either does reach the whole chain — by traversal now,
#: not by being written out.
DOWNSTREAM: dict[str, tuple[str, ...]] = {
    "settings": ("projects",),
    "projects": ("inventory",),
    "inventory": ("pricing",),
    "pricing": ("sales",),
    "sales": ("payment_plans", "unit_economics"),
    # Construction calls payment plans' milestone certification contract, so a
    # change to that contract can break construction. The edge is the code
    # relationship and not the roadmap order: construction came later, but that
    # is not why its tests run.
    "payment_plans": ("collections", "construction"),
    "collections": (),
    # Unit economics may source a construction forecast's hard-cost estimate at
    # completion through a named reader, so a construction change reaches it.
    "construction": ("unit_economics",),
    "unit_economics": (),
    "audit": (),
    "access": (),
}

#: Paths whose blast radius a targeted selection cannot honestly bound. A shared
#: fixture rewrites the ground every test stands on; the core defines the errors
#: and the session; the access layer decides who may call anything at all, and
#: PR-MVP-01 through -06 all lean on it. Changes here are rare and deserve the
#: whole suite.
#:
#: ``app/main.py`` and ``app/db/migrations/env.py`` are deliberately absent:
#: every new domain touches both by necessity, so treating them as full-risk
#: would mean no functional pull request ever got a fast cycle. Compilation, the
#: always-run smoke set and the migration run cover them.
FULL_RISK_PATHS = (
    "tests/conftest.py",
    "tests/modules/conftest.py",
    "tests/factories.py",
    "pyproject.toml",
    "pytest.ini",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    ".python-version",
)

FULL_RISK_PREFIXES = (
    "app/core/",
    "app/modules/access/",
)

#: Infrastructure under ``app/db/`` that is not a migration: the declarative
#: base, the naming convention, the session factory.
DB_INFRA_PREFIX = "app/db/"
MIGRATIONS_PREFIX = "app/db/migrations/"
MIGRATION_VERSIONS_PREFIX = "app/db/migrations/versions/"

#: Paths that cannot break a backend test on their own. They still run the
#: always-run set, because "cannot" is a claim worth checking cheaply.
#:
#: This list is deliberately short and explicit. Anything not named here and
#: not classified above is treated as unknown infrastructure and runs the full
#: suite — see :func:`select`. A generous allowlist would be the same mistake
#: as a generous default, made once instead of continuously.
INERT_PREFIXES = ("frontend/", "docs/", ".github/", ".vscode/")
INERT_SUFFIXES = (".md",)
INERT_FILES = (".gitignore", ".gitattributes", "LICENSE", "LICENSE.md", "LICENSE.txt")

#: The one script that decides which tests run, and the tests that prove it.
SELECTOR_SCRIPT = "scripts/ci_backend_tests.py"
SELECTOR_TESTS = "tests/test_ci_selector.py"


class Selection:
    """What to run, and the reasoning, in a form a log can print.

    A plain object rather than a dataclass: it carries four fields and is
    constructed in one place, and the import would be the larger half of it.
    """

    __slots__ = ("domains", "full", "paths", "reasons")

    def __init__(
        self,
        *,
        full: bool,
        paths: list[str],
        domains: list[str],
        reasons: list[str],
    ) -> None:
        self.full = full
        self.paths = paths
        self.domains = domains
        self.reasons = reasons


# --------------------------------------------------------------------------- #
# Classification — pure, and the part worth testing
# --------------------------------------------------------------------------- #


def domain_of_module_path(path: str) -> str | None:
    """The domain a file under ``app/modules/`` belongs to, if it is one."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "modules":
        return parts[2]
    return None


def domain_of_migration(path: str) -> str | None:
    """The domain a migration file names, read from its own revision name.

    ``0006_payment_plans.py`` is the payment plans schema, and a pull request
    that adds one is the ordinary shape of functional work — forcing the full
    suite for it would mean no functional pull request ever ran fast. A
    migration whose name matches no domain falls back, which is the right
    answer for one that reshapes something shared.
    """
    stem = Path(path).stem
    for domain in DOMAIN_TEST_PREFIXES:
        if stem.endswith(domain) or stem.endswith(domain.rstrip("s")):
            return domain
    if stem.endswith("_sales_legal"):
        return "sales"
    if stem.endswith("_project_land_permits"):
        return "projects"
    if stem.endswith("_governance_access"):
        return "access"
    return None


def closure(domains: set[str], graph: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """The changed domains plus everything reachable downstream of them.

    Transitive, by walking the edges. A change to pricing reaches sales, and
    through sales reaches payment plans, and through payment plans will reach
    collections the moment PR-MVP-07 adds that one edge — without anybody
    having to remember to widen pricing's own entry.

    The visited set makes this terminate even on a malformed graph. A cycle is
    still a bug, and :func:`find_cycle` is what fails the build over it; this
    function's job is to answer, not to hang.
    """
    edges = DOWNSTREAM if graph is None else graph
    reached: set[str] = set()
    pending = list(domains)
    while pending:
        domain = pending.pop()
        if domain in reached:
            continue
        reached.add(domain)
        pending.extend(edges.get(domain, ()))
    return sorted(reached)


def find_cycle(graph: dict[str, tuple[str, ...]] | None = None) -> list[str] | None:
    """The first dependency cycle in the graph, as a path, or ``None``.

    Downstream has to be a direction. A cycle of any length — not merely two
    domains naming each other — would make every change inside it select every
    other, quietly turning targeted mode back into the full suite while still
    reporting itself as targeted.

    Depth-first with three colours: unvisited, on the current path, finished.
    Meeting a domain that is on the current path is the cycle.
    """
    edges = DOWNSTREAM if graph is None else graph
    unvisited, on_path, done = 0, 1, 2
    colour: dict[str, int] = {}
    path: list[str] = []

    def walk(domain: str) -> list[str] | None:
        colour[domain] = on_path
        path.append(domain)
        for target in edges.get(domain, ()):
            state = colour.get(target, unvisited)
            if state == on_path:
                return [*path[path.index(target) :], target]
            if state == unvisited:
                found = walk(target)
                if found is not None:
                    return found
        colour[domain] = done
        path.pop()
        return None

    for domain in edges:
        if colour.get(domain, unvisited) == unvisited:
            found = walk(domain)
            if found is not None:
                return found
    return None


def tests_for_domain(domain: str, available: list[str]) -> list[str]:
    """Every existing test file claimed by one domain."""
    prefixes = DOMAIN_TEST_PREFIXES.get(domain)
    if not prefixes:
        return []
    chosen = []
    for path in available:
        name = Path(path).name
        if not name.startswith("test_"):
            continue
        stem = name[len("test_") : -len(".py")]
        if any(stem.startswith(prefix) for prefix in prefixes):
            chosen.append(path)
    return sorted(chosen)


def unclaimed_test_files(available: list[str]) -> list[str]:
    """Test files no domain claims and the always-run set does not name.

    A guard against the map rotting: a new test file that nothing selects would
    otherwise be quietly absent from every fast run, which is the failure mode
    that makes people stop trusting targeted CI.
    """
    claimed = set(ALWAYS_RUN) | {SELECTOR_TESTS}
    for domain in DOMAIN_TEST_PREFIXES:
        claimed.update(tests_for_domain(domain, available))
    return sorted(path for path in available if path not in claimed)


def select(changed: list[str], available: list[str]) -> Selection:
    """Decide what to run for one set of changed paths.

    Pure: it is handed the change and the test files that exist, and returns a
    decision. Nothing here reads a repository or starts a process, which is why
    the interesting cases can be tested without running fifteen hundred tests.
    """
    reasons: list[str] = []
    domains: set[str] = set()
    direct: set[str] = set()
    available_set = set(available)

    for path in sorted(set(changed)):
        if path in FULL_RISK_PATHS:
            reasons.append(f"{path} is shared by every test")
            continue
        if path.startswith(FULL_RISK_PREFIXES):
            reasons.append(f"{path} is cross-cutting infrastructure")
            continue

        if path.startswith(MIGRATION_VERSIONS_PREFIX):
            domain = domain_of_migration(path)
            if domain is None:
                reasons.append(f"{path} is a migration no domain claims")
            else:
                domains.add(domain)
            continue
        if path.startswith(MIGRATIONS_PREFIX):
            # env.py and friends: proved by the migration run itself.
            continue
        if path.startswith(DB_INFRA_PREFIX):
            reasons.append(f"{path} is database infrastructure")
            continue

        if path.startswith("tests/"):
            if Path(path).name.startswith("test_"):
                # A changed or new test always runs, whatever else selects.
                if path in available_set:
                    direct.add(path)
                continue
            reasons.append(f"{path} is shared test support")
            continue

        if path == SELECTOR_SCRIPT:
            if SELECTOR_TESTS in available_set:
                direct.add(SELECTOR_TESTS)
            continue
        if path.startswith("scripts/"):
            # Everything else under scripts/ builds or starts the deployed
            # application — render-build.sh and render-start.sh today. Treating
            # those as harmless CI tooling because of where they live is exactly
            # the kind of shortcut that ships a broken start command.
            reasons.append(f"{path} is operational infrastructure")
            continue

        if path in INERT_FILES:
            continue
        if path.startswith(INERT_PREFIXES) or path.endswith(INERT_SUFFIXES):
            continue

        if path.startswith("app/modules/"):
            domain = domain_of_module_path(path)
            if domain is None or domain not in DOMAIN_TEST_PREFIXES:
                reasons.append(f'unknown backend domain "{domain or path}"')
            else:
                domains.add(domain)
            continue

        if path == "app/main.py":
            # Every new domain mounts a router here. Compilation and the
            # always-run smoke set prove it.
            continue

        if path.startswith("app/"):
            reasons.append(f"{path} is application code no domain claims")
            continue

        # Anything left is unrecognised. alembic.ini, a Dockerfile, a Procfile,
        # render.yaml, a tool configuration nobody has classified yet — each can
        # change how the application is built, migrated or started. The stated
        # principle is known-harmless targeted, unknown full, so this is where
        # it is applied rather than quietly excepted.
        reasons.append(f"{path} is unclassified repository infrastructure")

    if reasons:
        return Selection(full=True, paths=["tests"], domains=[], reasons=reasons)

    reached = closure(domains)
    missing = [domain for domain in reached if not tests_for_domain(domain, available)]
    if missing:
        return Selection(
            full=True,
            paths=["tests"],
            domains=reached,
            reasons=[f"no test family exists for changed domain {name}" for name in missing],
        )

    paths = set(ALWAYS_RUN) & available_set
    paths |= direct
    for domain in reached:
        paths.update(tests_for_domain(domain, available))

    if not paths:
        # Cannot happen with a healthy checkout; if it does, the honest answer
        # is everything rather than a green tick over nothing.
        return Selection(
            full=True,
            paths=["tests"],
            domains=reached,
            reasons=["no test file could be resolved"],
        )
    return Selection(full=False, paths=sorted(paths), domains=reached, reasons=[])


# --------------------------------------------------------------------------- #
# The command
# --------------------------------------------------------------------------- #


def available_test_files(root: Path) -> list[str]:
    """Every test file in the checkout, as repository-relative paths."""
    return sorted(
        str(path.relative_to(root)) for path in root.glob("tests/**/test_*.py") if path.is_file()
    )


class CannotDiff(Exception):
    """Git could not tell us what changed, so nothing may be ruled out."""


def changed_files(base: str) -> list[str]:
    """Every path the pull request touches, against its merge base.

    The merge base and not the previous commit: a pull request is five commits
    as often as one, and a fast run that only understood the last patch would
    miss what the first four changed.

    A shallow checkout, a force-push or a base that is not in the object store
    all make this unanswerable. That is a reason to run everything, not a reason
    to guess — so it raises, and the caller falls back to the full suite.
    """
    try:
        merge_base = subprocess.run(
            ["git", "merge-base", base, "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "--name-only", f"{merge_base}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise CannotDiff(f"could not diff against {base}: {error}") from error
    return [line for line in diff.stdout.splitlines() if line]


def report(selection: Selection, changed: list[str]) -> str:
    """The decision, in the form somebody reading a failed run needs it."""
    lines = [f"Changed files: {len(changed)}"]
    for path in changed[:40]:
        lines.append(f"  {path}")
    if len(changed) > 40:
        lines.append(f"  … and {len(changed) - 40} more")
    lines.append("")
    if selection.full:
        lines.append("CI mode: full-fallback")
        lines.append("Reason:")
        for reason in selection.reasons:
            lines.append(f"  {reason}")
        lines.append("")
        lines.append("Running the entire backend suite.")
        return "\n".join(lines)

    lines.append("CI mode: targeted")
    lines.append("")
    lines.append("Domain closure (changed domains and everything downstream):")
    for domain in selection.domains or ["(none — always-run set only)"]:
        lines.append(f"  {domain}")
    lines.append("")
    lines.append(f"Selected test files: {len(selection.paths)}")
    for path in selection.paths:
        lines.append(f"  {path}")
    lines.append("")
    lines.append("The full suite runs when this pull request is marked ready for review.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main", help="branch to diff against")
    parser.add_argument(
        "--changed",
        nargs="*",
        help="classify these paths instead of asking git (for trying it out)",
    )
    parser.add_argument("--out", help="write the pytest arguments here, one per line")
    args = parser.parse_args(argv)

    available = available_test_files(ROOT)
    if not available:
        print("No test files found in the checkout — refusing to report success.")
        return 1

    if args.changed is not None:
        changed = args.changed
    else:
        try:
            changed = changed_files(args.base)
        except CannotDiff as error:
            print("CI mode: full-fallback")
            print(f"Reason:\n  {error}")
            print("\nRunning the entire backend suite.")
            if args.out:
                Path(args.out).write_text("tests\n")
            return 0

    selection = select(changed, available)
    print(report(selection, changed))

    if args.out:
        Path(args.out).write_text("\n".join(selection.paths) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
