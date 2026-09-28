"""Risk-based backend selection is explicit, direct, and fail-closed."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_backend_tests as selector  # noqa: E402

AVAILABLE = selector.available_test_files(ROOT)


def chosen(*paths: str) -> selector.Selection:
    return selector.select(list(paths), AVAILABLE)


def test_sales_change_runs_sales_and_direct_consumers_only() -> None:
    result = chosen("app/modules/sales/service.py")
    assert result.risk == "module"
    assert result.changed_domains == ["sales"]
    assert result.domains == ["payment_plans", "sales", "unit_economics"]
    assert not result.full and not result.error
    assert any("test_sales_" in path for path in result.paths)
    assert any("test_payment_plan" in path for path in result.paths)
    assert any("test_unit_economics" in path for path in result.paths)
    assert not any("test_collection_" in path for path in result.paths)
    assert not any(path.startswith("tests/modules/test_cashflow_") for path in result.paths)


def test_projects_change_stops_after_the_direct_neighbours() -> None:
    result = chosen("app/modules/projects/service.py")
    assert result.domains == ["cutover", "inventory", "management_actions", "projects"]
    assert "pricing" not in result.domains
    assert "sales" not in result.domains
    assert not result.full


def test_pricing_change_runs_pricing_and_sales_not_the_commercial_stack() -> None:
    result = chosen("app/modules/pricing/service.py")
    assert result.domains == ["pricing", "sales"]
    assert not {"payment_plans", "collections", "cashflow"} & set(result.domains)


def test_construction_change_has_the_documented_direct_consumers() -> None:
    result = chosen("app/modules/construction/service.py")
    assert result.domains == ["cashflow", "construction", "unit_economics"]


def test_two_changed_products_are_cross_domain_without_becoming_full() -> None:
    result = chosen(
        "app/modules/pricing/service.py",
        "app/modules/collections/service.py",
    )
    assert result.risk == "cross-domain"
    assert result.changed_domains == ["collections", "pricing"]
    assert result.domains == ["cashflow", "collections", "pricing", "sales"]
    assert not result.full


def test_new_domain_migration_adds_migration_and_invariant_packs_not_full() -> None:
    result = chosen(
        "app/modules/projects/models.py",
        "app/db/migrations/versions/0039_projects.py",
    )
    assert result.risk == "module"
    assert result.migration
    assert result.migrations == ["0039_projects.py"]
    assert "tests/test_migrations.py" in result.paths
    assert "tests/modules/test_migration_projects.py" in result.paths
    assert "tests/modules/test_cutover_intake_contract.py" in result.paths
    assert "tests/test_deletion_contracts.py" in result.paths
    assert not result.full


def test_unknown_product_module_is_an_actionable_plan_error() -> None:
    result = chosen("app/modules/foo/service.py")
    assert result.error
    assert "CI PLAN ERROR" in result.error
    assert "app/modules/foo/" in result.error
    assert "scripts/ci_backend_tests.py" in result.error
    assert not result.full


def test_unknown_product_module_cli_fails_without_writing_a_plan(tmp_path: Path) -> None:
    output = tmp_path / "selected.txt"
    code = selector.main(
        ["--changed", "app/modules/foo/service.py", "--out", str(output), "--github-output", ""]
    )
    assert code == 2
    assert not output.exists()


@pytest.mark.parametrize(
    "path",
    [
        "app/core/database.py",
        "app/db/base.py",
        "app/db/migrations/env.py",
        "app/modules/access/service.py",
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        "pytest.ini",
        "tests/conftest.py",
    ],
)
def test_foundational_change_is_system_risk(path: str) -> None:
    result = chosen(path)
    assert result.risk == "system"
    assert result.full
    assert result.paths == ["tests"]
    assert result.reasons


@pytest.mark.parametrize(
    "path",
    [
        "scripts/ci_backend_tests.py",
        "scripts/ci_backend_shards.py",
        ".github/workflows/ci.yml",
        ".github/workflows/full-backend-shadow.yml",
    ],
)
def test_ci_tooling_runs_ci_guards_without_product_full(path: str) -> None:
    result = chosen(path)
    assert result.risk == "module"
    assert not result.full
    assert "tests/test_ci_selector.py" in result.paths
    assert "tests/test_ci_workflow.py" in result.paths


@pytest.mark.parametrize("path", ["docs/CI_STRATEGY.md", "README.md", "frontend/src/app/page.tsx"])
def test_docs_and_frontend_only_need_no_backend_runner(path: str) -> None:
    result = chosen(path)
    assert result.risk == "none"
    assert not result.backend_required
    assert result.paths == []
    assert not result.full


def test_invariant_pack_retains_platform_wide_contracts() -> None:
    required = {
        "tests/test_config.py",
        "tests/test_migrations.py",
        "tests/modules/test_auth.py",
        "tests/modules/test_authorization.py",
        "tests/modules/test_audit.py",
        "tests/modules/test_strict_requests.py",
        "tests/test_ci_selector.py",
        "tests/test_ci_workflow.py",
        "tests/test_ci_smoke.py",
        "tests/test_ci_shards.py",
        "tests/test_test_isolation.py",
        "tests/test_deletion_contracts.py",
        "tests/modules/test_cutover_intake_contract.py",
        "tests/test_agent_guardrails.py",
        "tests/test_pr_quality.py",
    }
    assert required <= set(selector.ALWAYS_RUN)
    assert required <= set(chosen("app/modules/pricing/service.py").paths)


def test_every_product_module_is_registered() -> None:
    modules = {
        path.name
        for path in (ROOT / "app/modules").iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    assert modules <= set(selector.DOMAIN_TEST_PREFIXES)


def test_every_domain_has_tests_and_every_test_is_claimed() -> None:
    for domain in selector.DOMAIN_TEST_PREFIXES:
        assert selector.tests_for_domain(domain, AVAILABLE), domain
    assert selector.unclaimed_test_files(AVAILABLE) == []


def test_direct_consumer_registry_is_valid_and_acyclic() -> None:
    for source, targets in selector.DOWNSTREAM.items():
        assert source in selector.DOMAIN_TEST_PREFIXES
        assert set(targets) <= set(selector.DOMAIN_TEST_PREFIXES)
        assert source not in targets
    assert selector.find_cycle() is None


def test_closure_is_exactly_one_hop_even_for_a_chain() -> None:
    graph = {"a": ("b",), "b": ("c",), "c": ()}
    assert selector.closure({"a"}, graph) == ["a", "b"]
    assert selector.closure({"b"}, graph) == ["b", "c"]


def test_edge_contract_registry_is_ready_for_narrow_contract_packs() -> None:
    for (producer, consumer), paths in selector.EDGE_CONTRACT_TESTS.items():
        assert consumer in selector.DOWNSTREAM[producer]
        assert set(paths) <= set(AVAILABLE)


def test_report_explains_risk_domains_migration_and_full_decision() -> None:
    result = chosen("app/modules/pricing/service.py")
    plan = selector.report(result, ["app/modules/pricing/service.py"])
    assert "CI BACKEND PLAN" in plan
    assert "Risk: module" in plan
    assert "Changed domains:\n- pricing" in plan
    assert "Selected domains (changed + direct consumers):" in plan
    assert "Full regression:\n- not required" in plan
    assert "Selected test files:" in plan


def test_github_outputs_are_machine_readable(tmp_path: Path) -> None:
    output = tmp_path / "github-output.txt"
    selector.write_github_output(str(output), chosen("app/modules/pricing/service.py"))
    values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    assert values["risk"] == "module"
    assert values["backend_required"] == "true"
    assert values["full_required"] == "false"
    assert values["domains"] == '["pricing","sales"]'
