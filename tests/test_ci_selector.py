"""The test selector's own tests.

A targeted CI run is only worth having if the thing doing the targeting is
itself proved. An untested selector is a machine that quietly stops running the
tests that would have caught the bug — the exact failure that makes people give
up on selective CI and go back to waiting forty minutes.

These are pure: they hand :func:`select` a change and a list of test files and
read the decision. Nothing here starts a process or touches a database, so the
whole file runs in well under a second and belongs in the always-run set.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Imported as a module rather than by name: pytest collects any callable in a
# test module whose name begins with "test", and `selector.tests_for_domain` is one.
import ci_backend_tests as selector  # noqa: E402

ALWAYS_RUN = selector.ALWAYS_RUN
select = selector.select

#: A stand-in checkout: enough real file names to exercise the map without
#: depending on the suite's exact contents on any given day.
AVAILABLE = [
    "tests/test_config.py",
    "tests/test_health.py",
    "tests/test_migrations.py",
    "tests/test_static_frontend.py",
    "tests/test_ux_copy.py",
    "tests/test_ci_selector.py",
    "tests/modules/test_audit.py",
    "tests/modules/test_auth.py",
    "tests/modules/test_authorization.py",
    "tests/modules/test_docs_exposure.py",
    "tests/modules/test_strict_requests.py",
    "tests/modules/test_settings.py",
    "tests/modules/test_projects.py",
    "tests/modules/test_permits.py",
    "tests/modules/test_parcels.py",
    "tests/modules/test_units.py",
    "tests/modules/test_phases.py",
    "tests/modules/test_inventory_integrity.py",
    "tests/modules/test_pricing_calculator.py",
    "tests/modules/test_price_versions.py",
    "tests/modules/test_sales_legal.py",
    "tests/modules/test_sale_contracts.py",
    "tests/modules/test_reservations.py",
    "tests/modules/test_payment_plans.py",
    "tests/modules/test_payment_plan_register.py",
    "tests/modules/test_migration_payment_plans.py",
    "tests/modules/test_collection_receipts.py",
    "tests/modules/test_collection_allocations.py",
    "tests/modules/test_collection_aging.py",
    "tests/modules/test_collection_status.py",
    "tests/modules/test_collection_restructures.py",
    "tests/modules/test_migration_collections.py",
    "tests/modules/test_unit_economics_calculator.py",
    "tests/modules/test_unit_economics_allocation.py",
    "tests/modules/test_unit_economics_profitability.py",
    "tests/modules/test_unit_economics_security.py",
    "tests/modules/test_unit_economics_concurrency.py",
    "tests/modules/test_migration_unit_economics.py",
]

SMOKE = sorted(set(ALWAYS_RUN) & set(AVAILABLE))


def chosen(*changed: str) -> object:
    return select(list(changed), AVAILABLE)


# --------------------------------------------------------------------------- #
# Targeted selection
# --------------------------------------------------------------------------- #


def test_a_payment_plan_change_runs_payment_plans_and_not_the_rest() -> None:
    """The case this exists for: a surgical change and its downstream consumer.

    Payment plans feeds collections, so collections comes with it. Nothing
    upstream does — sales, pricing, inventory and land are all unreachable
    from here, which is where the time is saved.
    """
    result = chosen("app/modules/payment_plans/service.py")

    assert result.full is False
    assert result.domains == ["collections", "payment_plans"]
    assert "tests/modules/test_payment_plans.py" in result.paths
    assert "tests/modules/test_payment_plan_register.py" in result.paths
    assert "tests/modules/test_migration_payment_plans.py" in result.paths
    # Land, permits and pricing cannot be reached from here.
    assert "tests/modules/test_permits.py" not in result.paths
    assert "tests/modules/test_parcels.py" not in result.paths
    assert "tests/modules/test_pricing_calculator.py" not in result.paths
    assert "tests/modules/test_sales_legal.py" not in result.paths


def test_the_always_run_set_is_in_every_targeted_selection() -> None:
    result = chosen("app/modules/payment_plans/service.py")
    assert set(SMOKE).issubset(set(result.paths))


def test_a_sales_change_reaches_payment_plans_but_not_pricing() -> None:
    """Downstream, never upstream. This asymmetry is the whole saving."""
    result = chosen("app/modules/sales/service.py")

    assert result.full is False
    assert result.domains == ["collections", "payment_plans", "sales", "unit_economics"]
    assert "tests/modules/test_sales_legal.py" in result.paths
    assert "tests/modules/test_payment_plans.py" in result.paths
    assert "tests/modules/test_unit_economics_profitability.py" in result.paths
    assert "tests/modules/test_pricing_calculator.py" not in result.paths
    assert "tests/modules/test_units.py" not in result.paths


def test_a_pricing_change_reaches_sales_and_payment_plans() -> None:
    result = chosen("app/modules/pricing/service.py")

    assert result.domains == [
        "collections",
        "payment_plans",
        "pricing",
        "sales",
        "unit_economics",
    ]
    assert "tests/modules/test_pricing_calculator.py" in result.paths
    assert "tests/modules/test_sale_contracts.py" in result.paths
    assert "tests/modules/test_payment_plans.py" in result.paths
    assert "tests/modules/test_unit_economics_allocation.py" in result.paths
    assert "tests/modules/test_units.py" not in result.paths


def test_an_inventory_change_reaches_everything_it_feeds() -> None:
    result = chosen("app/modules/inventory/models.py")

    assert result.domains == [
        "collections",
        "inventory",
        "payment_plans",
        "pricing",
        "sales",
        "unit_economics",
    ]
    assert "tests/modules/test_units.py" in result.paths
    assert "tests/modules/test_payment_plans.py" in result.paths
    assert "tests/modules/test_unit_economics_allocation.py" in result.paths
    # Projects sits above inventory, so it is not re-proved by this change.
    assert "tests/modules/test_permits.py" not in result.paths


def test_two_changed_domains_select_the_union_of_both_closures() -> None:
    result = chosen(
        "app/modules/sales/api.py",
        "app/modules/inventory/api.py",
    )
    assert result.domains == [
        "collections",
        "inventory",
        "payment_plans",
        "pricing",
        "sales",
        "unit_economics",
    ]


def test_a_unit_economics_change_runs_only_unit_economics() -> None:
    """The direction is one way, and this is the test that keeps it that way.

    Unit economics reads projects, inventory, pricing and sales. Reading is not
    a reason to re-prove them: its own tests already exercise its use of their
    public contracts, and selecting them here would give the module that arrives
    last the slowest cycle in the repository.
    """
    result = chosen("app/modules/unit_economics/calculator.py")

    assert result.full is False
    assert result.domains == ["unit_economics"]
    assert "tests/modules/test_unit_economics_calculator.py" in result.paths
    for upstream in (
        "tests/modules/test_sale_contracts.py",
        "tests/modules/test_pricing_calculator.py",
        "tests/modules/test_units.py",
        "tests/modules/test_permits.py",
        "tests/modules/test_collection_receipts.py",
    ):
        assert upstream not in result.paths


def test_unit_economics_is_not_reached_from_collections() -> None:
    """Roadmap order is not a dependency. PR-MVP-07 came first and feeds nothing here."""
    result = chosen("app/modules/collections/service.py")

    assert result.domains == ["collections"]
    assert "tests/modules/test_unit_economics_allocation.py" not in result.paths


# --------------------------------------------------------------------------- #
# Tests themselves
# --------------------------------------------------------------------------- #


def test_a_changed_test_file_always_runs() -> None:
    """Even when no application change would have selected it."""
    result = chosen("tests/modules/test_permits.py")

    assert result.full is False
    assert "tests/modules/test_permits.py" in result.paths
    assert result.domains == []


def test_a_changed_test_runs_alongside_the_domain_that_selected_it() -> None:
    result = chosen(
        "app/modules/payment_plans/service.py",
        "tests/modules/test_permits.py",
    )
    assert "tests/modules/test_permits.py" in result.paths
    assert "tests/modules/test_payment_plans.py" in result.paths


def test_a_test_file_that_does_not_exist_yet_is_not_passed_to_pytest() -> None:
    """A deleted test must not become a path pytest cannot open.

    The change list names it because the pull request touched it; the checkout
    is the authority on whether it is still there.
    """
    result = chosen("tests/modules/test_deleted_thing.py")
    assert "tests/modules/test_deleted_thing.py" not in result.paths
    assert result.paths == SMOKE


def test_changing_the_selector_runs_the_selector_tests() -> None:
    result = chosen("scripts/ci_backend_tests.py")
    assert result.full is False
    assert "tests/test_ci_selector.py" in result.paths


# --------------------------------------------------------------------------- #
# Falling back
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        "tests/conftest.py",
        "tests/modules/conftest.py",
        "tests/factories.py",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
    ],
)
def test_shared_test_and_dependency_files_fall_back_to_the_full_suite(path: str) -> None:
    result = chosen(path)
    assert result.full is True
    assert result.paths == ["tests"]
    assert result.reasons


@pytest.mark.parametrize(
    "path",
    [
        "app/core/errors.py",
        "app/core/config.py",
        "app/modules/access/permissions.py",
        "app/db/base.py",
        "app/db/session.py",
    ],
)
def test_cross_cutting_infrastructure_falls_back_to_the_full_suite(path: str) -> None:
    """Who may call what, and what a session is, cannot be bounded by a domain."""
    result = chosen(path)
    assert result.full is True


def test_an_unknown_backend_domain_falls_back_and_says_which() -> None:
    """Fail safe, not fail open: a new module runs everything until it is mapped.

    ``collections`` was the example here, then ``unit_economics``, and both are
    real domains now. The example keeps moving on purpose: the guard applies to
    whatever module arrives next, not to a name somebody wrote down once.
    """
    result = chosen("app/modules/construction/service.py")

    assert result.full is True
    assert any("construction" in reason for reason in result.reasons)


def test_a_mapped_domain_with_no_test_family_falls_back() -> None:
    """A domain that should have tests and has none is a finding, not a pass."""
    thin = [path for path in AVAILABLE if "payment_plan" not in path]
    result = select(["app/modules/payment_plans/service.py"], thin)

    assert result.full is True
    assert any("payment_plans" in reason for reason in result.reasons)


def test_application_code_outside_a_domain_falls_back() -> None:
    result = chosen("app/some_new_layer/thing.py")
    assert result.full is True


# --------------------------------------------------------------------------- #
# Migrations, and the two files every domain necessarily touches
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("0008_unit_economics.py", "unit_economics"),
        ("0007_collections.py", "collections"),
        ("0006_payment_plans.py", "payment_plans"),
        ("0005_sales_legal.py", "sales"),
        ("0004_pricing.py", "pricing"),
        ("0003_inventory.py", "inventory"),
        ("0002_project_land_permits.py", "projects"),
        ("0001_governance_access.py", "access"),
        ("0010_something_shared.py", None),
    ],
)
def test_a_migration_is_read_for_the_domain_it_names(filename: str, expected: str | None) -> None:
    assert selector.domain_of_migration(f"app/db/migrations/versions/{filename}") == expected


def test_adding_a_domains_own_migration_does_not_force_the_full_suite() -> None:
    """The ordinary shape of functional work, and the case that must stay fast.

    Every roadmap pull request adds a migration, mounts a router in main.py and
    imports its models in the migration environment. If any of those forced a
    full run, no functional pull request would ever get a fast cycle.
    """
    result = chosen(
        "app/modules/unit_economics/models.py",
        "app/db/migrations/versions/0008_unit_economics.py",
        "app/db/migrations/env.py",
        "app/main.py",
    )
    assert result.full is False
    assert result.domains == ["unit_economics"]


def test_a_migration_no_domain_claims_falls_back() -> None:
    result = chosen("app/db/migrations/versions/0010_rework_currencies.py")
    assert result.full is True


# --------------------------------------------------------------------------- #
# Changes that cannot break a backend test
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        "docs/ENGINEERING_RULES.md",
        "README.md",
        "frontend/src/components/projects/PaymentPlansTab.tsx",
        "frontend/package.json",
        ".github/workflows/ci.yml",
    ],
)
def test_documentation_and_frontend_run_only_the_always_run_set(path: str) -> None:
    result = chosen(path)
    assert result.full is False
    assert result.paths == SMOKE


def test_an_empty_change_still_runs_the_always_run_set() -> None:
    """Never zero tests collected under a green tick."""
    result = select([], AVAILABLE)
    assert result.full is False
    assert result.paths == SMOKE


def test_a_checkout_with_no_tests_falls_back_rather_than_passing() -> None:
    result = select(["docs/README.md"], [])
    assert result.full is True


# --------------------------------------------------------------------------- #
# Shape of the output
# --------------------------------------------------------------------------- #


def test_selected_paths_are_sorted_and_free_of_duplicates() -> None:
    result = chosen(
        "app/modules/sales/service.py",
        "app/modules/sales/api.py",
        "tests/modules/test_sales_legal.py",
    )
    assert result.paths == sorted(result.paths)
    assert len(result.paths) == len(set(result.paths))


def test_every_selected_path_exists_in_the_checkout() -> None:
    result = chosen("app/modules/payment_plans/service.py")
    assert set(result.paths).issubset(set(AVAILABLE))


def test_the_report_names_the_mode_and_the_reason() -> None:
    change = ["app/modules/sales/service.py"]
    targeted = selector.report(chosen(*change), change)
    assert "CI mode: targeted" in targeted
    assert "payment_plans" in targeted

    fallback = selector.report(chosen("tests/modules/conftest.py"), ["tests/modules/conftest.py"])
    assert "CI mode: full-fallback" in fallback
    assert "shared by every test" in fallback


# --------------------------------------------------------------------------- #
# The map against the real repository
# --------------------------------------------------------------------------- #


def test_every_test_file_in_the_repository_is_claimed_by_something() -> None:
    """The guard that keeps the map from rotting.

    A test file no domain claims would be absent from every targeted run and
    nobody would notice, because a passing run looks the same either way. Adding
    a test family without adding it to the map fails here instead.
    """
    unclaimed = selector.unclaimed_test_files(selector.available_test_files(ROOT))
    assert unclaimed == [], (
        "these test files belong to no domain — add them to selector.DOMAIN_TEST_PREFIXES "
        f"or to ALWAYS_RUN: {unclaimed}"
    )


def test_every_domain_in_the_map_has_tests_in_the_repository() -> None:
    available = selector.available_test_files(ROOT)
    empty = [
        name
        for name in selector.DOMAIN_TEST_PREFIXES
        if not selector.tests_for_domain(name, available)
    ]
    assert empty == [], f"domains mapped but with no test family: {empty}"


def test_every_downstream_target_is_a_known_domain() -> None:
    for domain, targets in selector.DOWNSTREAM.items():
        for target in targets:
            assert target in selector.DOMAIN_TEST_PREFIXES, (
                f"{domain} feeds unknown domain {target}"
            )


def test_the_real_dependency_map_has_no_cycle_of_any_length() -> None:
    """Downstream must be a direction, not a loop.

    A cycle would make every change inside it select every other, quietly
    turning targeted mode back into the full suite while still calling itself
    targeted. Two domains naming each other is the obvious case; three is just
    as broken and considerably easier to introduce by accident.
    """
    assert selector.find_cycle() is None


# --------------------------------------------------------------------------- #
# The dependency graph, on synthetic shapes
# --------------------------------------------------------------------------- #

CHAIN = {"a": ("b",), "b": ("c",), "c": ()}
LOOP = {"a": ("b",), "b": ("c",), "c": ("a",)}
LONG_LOOP = {"a": ("b",), "b": ("c",), "c": ("d",), "d": ("b",)}
DIAMOND = {"a": ("b", "c"), "b": ("d",), "c": ("d",), "d": ()}


def test_closure_follows_the_chain_all_the_way_down() -> None:
    """Transitive, not one level. This is what stops the map needing every
    descendant written out by hand."""
    assert selector.closure({"a"}, CHAIN) == ["a", "b", "c"]
    assert selector.closure({"b"}, CHAIN) == ["b", "c"]
    assert selector.closure({"c"}, CHAIN) == ["c"]


def test_closure_visits_a_shared_descendant_once() -> None:
    assert selector.closure({"a"}, DIAMOND) == ["a", "b", "c", "d"]


def test_closure_terminates_on_a_malformed_graph() -> None:
    """A cycle is a bug the tests catch, not a reason for CI to hang."""
    assert selector.closure({"a"}, LOOP) == ["a", "b", "c"]


def test_a_three_node_cycle_is_detected() -> None:
    cycle = selector.find_cycle(LOOP)
    assert cycle is not None
    assert cycle[0] == cycle[-1], "a cycle is reported as a closed path"
    assert set(cycle) == {"a", "b", "c"}


def test_a_cycle_that_does_not_include_the_entry_point_is_detected() -> None:
    """b → c → d → b, reached from a. Depth-first has to notice on the way."""
    cycle = selector.find_cycle(LONG_LOOP)
    assert cycle is not None
    assert set(cycle) == {"b", "c", "d"}


def test_an_acyclic_graph_reports_no_cycle() -> None:
    assert selector.find_cycle(CHAIN) is None
    assert selector.find_cycle(DIAMOND) is None


def test_collections_is_reached_from_pricing_through_the_real_map() -> None:
    """PR-ENG-01 predicted this shape; PR-MVP-07 and -08 are it, on the real map.

    Adding collections was two lines — one entry in DOMAIN_TEST_PREFIXES and one
    edge, ``payment_plans -> collections``. Adding unit economics was two more,
    with its edge from sales. Nobody had to widen pricing, inventory, projects
    or settings either time, because the closure is transitive. That was the
    whole point of the fail-safe patch, and this is the case that proves it on
    the map the build actually uses.
    """
    assert selector.closure({"pricing"}) == [
        "collections",
        "payment_plans",
        "pricing",
        "sales",
        "unit_economics",
    ]

    assert selector.closure({"sales"}) == [
        "collections",
        "payment_plans",
        "sales",
        "unit_economics",
    ]
    assert selector.closure({"payment_plans"}) == ["collections", "payment_plans"]
    # And still downstream only: neither leaf drags sales back in.
    assert selector.closure({"collections"}) == ["collections"]
    assert selector.closure({"unit_economics"}) == ["unit_economics"]
    assert selector.find_cycle() is None


def test_a_collections_change_runs_collections_and_nothing_upstream() -> None:
    """The case PR-MVP-07 lives in, and the fastest one the selector has.

    Nothing is downstream of collections yet, so an ordinary change to it
    selects its own family and the always-run backbone — and none of pricing,
    sales or payment plans, whose own tests already prove the public contracts
    collections consumes.
    """
    result = chosen("app/modules/collections/service.py")

    assert result.full is False
    assert result.domains == ["collections"]
    assert "tests/modules/test_collection_receipts.py" in result.paths
    assert "tests/modules/test_collection_allocations.py" in result.paths
    assert "tests/modules/test_collection_restructures.py" in result.paths
    assert "tests/modules/test_migration_collections.py" in result.paths
    assert "tests/modules/test_payment_plans.py" not in result.paths
    assert "tests/modules/test_sales_legal.py" not in result.paths
    assert "tests/modules/test_pricing_calculator.py" not in result.paths


def test_a_payment_plan_change_now_reaches_collections() -> None:
    """One new edge, and the schedule's downstream consumer comes with it."""
    result = chosen("app/modules/payment_plans/service.py")

    assert result.domains == ["collections", "payment_plans"]
    assert "tests/modules/test_collection_restructures.py" in result.paths
    assert "tests/modules/test_payment_plans.py" in result.paths
    assert "tests/modules/test_sales_legal.py" not in result.paths


def test_a_sales_change_reaches_collections_transitively() -> None:
    """Two hops, no edge from sales to collections anywhere in the map."""
    result = chosen("app/modules/sales/service.py")

    assert result.domains == ["collections", "payment_plans", "sales", "unit_economics"]
    assert "tests/modules/test_collection_status.py" in result.paths
    assert "tests/modules/test_pricing_calculator.py" not in result.paths


def test_a_pricing_change_reaches_collections_through_three_hops() -> None:
    result = chosen("app/modules/pricing/service.py")

    assert result.domains == [
        "collections",
        "payment_plans",
        "pricing",
        "sales",
        "unit_economics",
    ]
    assert "tests/modules/test_collection_aging.py" in result.paths
    assert "tests/modules/test_units.py" not in result.paths


# --------------------------------------------------------------------------- #
# Scripts are not all the same kind of thing
# --------------------------------------------------------------------------- #


def test_changing_the_selector_script_runs_the_selector_tests_only() -> None:
    result = chosen(selector.SELECTOR_SCRIPT)
    assert result.full is False
    assert selector.SELECTOR_TESTS in result.paths


@pytest.mark.parametrize(
    "path",
    [
        "scripts/render-start.sh",
        "scripts/render-build.sh",
        "scripts/some_future_operational_script.py",
    ],
)
def test_operational_scripts_fall_back_to_the_full_suite(path: str) -> None:
    """These build and start the deployed application.

    Treating them as harmless CI tooling because of the directory they share
    with the selector is how a broken start command reaches production behind a
    green tick.
    """
    result = chosen(path)
    assert result.full is True
    assert any("operational infrastructure" in reason for reason in result.reasons)


# --------------------------------------------------------------------------- #
# Unknown is not the same as harmless
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        "render.yaml",
        "Dockerfile",
        "Procfile",
        "alembic.ini",
        "deployment.toml",
        "some_new_tool_config",
    ],
)
def test_unclassified_infrastructure_falls_back_to_the_full_suite(path: str) -> None:
    """Known harmless is targeted; unknown is everything.

    A file nobody has classified may change how the application is built,
    migrated or started, and the cost of being wrong in the safe direction is
    minutes.
    """
    result = chosen(path)
    assert result.full is True
    assert any("unclassified repository infrastructure" in reason for reason in result.reasons)


@pytest.mark.parametrize(
    "path",
    [".gitignore", ".gitattributes", "LICENSE", "LICENSE.md"],
)
def test_named_inert_files_stay_targeted(path: str) -> None:
    result = chosen(path)
    assert result.full is False
    assert result.paths == SMOKE


def test_closure_is_stable_when_applied_twice() -> None:
    once = selector.closure({"pricing"})
    twice = selector.closure(set(once))
    assert once == twice
