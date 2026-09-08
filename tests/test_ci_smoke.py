"""Integration selection is deliberately small and refuses unknown/shared risk."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_backend_smoke as smoke  # noqa: E402


def test_every_registered_contract_resolves_to_real_tests() -> None:
    smoke.validate_contract(smoke.BACKBONE)
    for nodes in smoke.DOMAIN_SMOKE.values():
        smoke.validate_contract(nodes)
    for owner, nodes in smoke.MIGRATIONS.values():
        assert owner in smoke.DOMAIN_SMOKE
        smoke.validate_contract(nodes)


def test_every_existing_module_is_owned_or_explicitly_full_risk() -> None:
    domains = {
        p.name
        for p in (ROOT / "app/modules").iterdir()
        if p.is_dir() and not p.name.startswith("_")
    }
    assert domains <= set(smoke.DOMAIN_SMOKE) | {"access"}


def test_backbone_is_explicit_and_does_not_inherit_fast() -> None:
    nodes, domains = smoke.select(["docs/example.md"])
    assert nodes == sorted(smoke.BACKBONE)
    assert not domains
    assert len(smoke.BACKBONE) <= 24
    assert not set(smoke.GUARDS) & set(smoke.BACKBONE)
    assert not any(node == "tests" for node in nodes)


@pytest.mark.parametrize("domain", sorted(smoke.DOMAIN_SMOKE))
def test_only_direct_contract_runs(domain: str) -> None:
    nodes, domains = smoke.select([f"app/modules/{domain}/service.py"])
    assert domains == [domain]
    assert set(nodes) == set(smoke.BACKBONE) | set(smoke.DOMAIN_SMOKE[domain])


@pytest.mark.parametrize(
    "path",
    [
        "app/core/config.py",
        "app/modules/access/service.py",
        "tests/conftest.py",
        "tests/modules/conftest.py",
        "tests/factories.py",
        "requirements.txt",
        "requirements-dev.txt",
        "pytest.ini",
        "pyproject.toml",
        "app/db/base.py",
        "app/db/migrations/env.py",
        "app/modules/inventory/custom_fields.py",
        ".github/workflows/ci.yml",
        "render.yaml",
        "scripts/render-start.sh",
    ],
)
def test_full_risk_refuses_instead_of_downgrading_or_running_full(path: str) -> None:
    with pytest.raises(smoke.SmokeRefused, match=r"full-gate|blast radius"):
        smoke.select([path])


def test_migration_environment_is_allowed_only_with_a_registered_migration() -> None:
    nodes, domains = smoke.select(
        [
            "app/db/migrations/env.py",
            "app/db/migrations/versions/0017_consultant_commissions.py",
        ]
    )
    assert "consultant_engineering" in domains
    assert (
        "tests/test_migrations.py::test_the_history_round_trips_from_empty_to_head_and_back"
        in nodes
    )


def test_new_domain_refuses_until_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    path = "app/modules/commissions/service.py"
    monkeypatch.delitem(smoke.DOMAIN_SMOKE, "commissions")
    with pytest.raises(smoke.SmokeRefused, match=r"commissions.*no Backend Smoke contract"):
        smoke.select([path])
    representative = ("tests/test_config.py::test_defaults_describe_the_service",)
    monkeypatch.setitem(smoke.DOMAIN_SMOKE, "commissions", representative)
    nodes, domains = smoke.select([path])
    assert domains == ["commissions"] and set(representative) <= set(nodes)


def test_missing_or_empty_contract_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(smoke.DOMAIN_SMOKE, "sales", ())
    with pytest.raises(smoke.SmokeRefused):
        smoke.select(["app/modules/sales/service.py"])
    with pytest.raises(smoke.SmokeRefused, match="Missing smoke test"):
        smoke.validate_contract(["tests/test_config.py::test_does_not_exist"])


def test_migrations_need_explicit_ownership_and_integrity_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = "app/db/migrations/versions/0016_projects_example.py"
    with pytest.raises(smoke.SmokeRefused, match="Unclassified migration"):
        smoke.select([path])
    integrity = ("tests/modules/test_migration_projects.py::test_the_revision_round_trips",)
    monkeypatch.setitem(smoke.MIGRATIONS, "0016_projects_example.py", ("projects", integrity))
    nodes, domains = smoke.select([path])
    assert domains == ["projects"] and set(integrity) <= set(nodes)


def test_unclassifiable_test_support_cannot_silently_pass() -> None:
    with pytest.raises(smoke.SmokeRefused):
        smoke.select(["tests/shared/helper.py"])


def test_presentation_contract_has_exact_ownership_and_runs_when_changed() -> None:
    path = "tests/test_product_experience.py"
    nodes, domains = smoke.select([path, "frontend/src/components/ui/Card.tsx"])
    assert not domains
    assert set(nodes) == set(smoke.BACKBONE) | {path}
    with pytest.raises(smoke.SmokeRefused, match="Unclassified/shared test"):
        smoke.select(["tests/test_product_experience_unreviewed.py"])
    with pytest.raises(smoke.SmokeRefused, match=r"full-gate|blast radius"):
        smoke.select([path, "tests/conftest.py"])


def test_a_large_domain_regression_file_does_not_turn_smoke_into_fast() -> None:
    nodes, domains = smoke.select(["tests/modules/test_collection_receipts.py"])
    assert domains == ["collections"]
    assert "tests/modules/test_collection_receipts.py" not in nodes


def test_cli_failure_is_nonzero_and_does_not_write_a_selection(tmp_path: Path) -> None:
    output = tmp_path / "selected.txt"
    assert smoke.main(["--changed", "app/core/database.py", "--out", str(output)]) == 1
    assert not output.exists()


@pytest.mark.parametrize(
    "scenario",
    [
        "exact",
        "extra-timeout",
        "extra-permission",
        "wildcard",
        "missing-test",
        "other-github",
        "file-mode",
        "no-explicit-base",
        "changed-override",
        "invalid-base",
        "only-one-substitution",
    ],
)
def test_reviewed_workflow_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    """Exercise real git deltas and the CLI boundary, including untrusted path overrides."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Smoke regression")
    git("config", "user.email", "smoke@example.invalid")
    git("config", "core.autocrlf", "false")
    git("config", "core.filemode", "false")
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    old_trigger = "    branches: [main, integration/mvp3]"
    new_trigger = "    branches: [main, integration/mvp3, integration/mvp3-management]"
    old_condition = (
        "    if: github.event_name == 'pull_request' && "
        "github.event.pull_request.base.ref == 'integration/mvp3'"
    )
    new_condition = (
        "    if: github.event_name == 'pull_request' && "
        "(github.event.pull_request.base.ref == 'integration/mvp3' || "
        "github.event.pull_request.base.ref == 'integration/mvp3-management')"
    )
    reviewed = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert reviewed.count(new_trigger) == reviewed.count(new_condition) == 1
    original = reviewed.replace(new_trigger, old_trigger).replace(new_condition, old_condition)
    workflow.write_text(original, encoding="utf-8")
    companion = tmp_path / "tests/test_ci_workflow.py"
    companion.parent.mkdir()
    companion.write_text("# Original lane contracts\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "Base")
    base = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/integration/mvp3", base)

    candidate = reviewed
    if scenario == "extra-timeout":
        candidate = candidate.replace("timeout-minutes: 30", "timeout-minutes: 31")
    elif scenario == "extra-permission":
        candidate = candidate.replace("contents: read", "contents: write")
    elif scenario == "wildcard":
        candidate = candidate.replace("integration/mvp3-management", "integration/*")
    elif scenario == "only-one-substitution":
        candidate = candidate.replace(new_condition, old_condition)
    workflow.write_text(candidate, encoding="utf-8")
    if scenario != "missing-test":
        companion.write_text("# Extended exact lane contracts\n", encoding="utf-8")
    if scenario == "other-github":
        (workflow.parent / "other.yml").write_text("name: unreviewed\n", encoding="utf-8")
    git("add", ".")
    if scenario == "file-mode":
        git("update-index", "--chmod=+x", ".github/workflows/ci.yml")
    git("commit", "-m", "Candidate")
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "selected.txt"
    args = ["--out", str(output)]
    if scenario != "no-explicit-base":
        args += ["--base", "missing-ref" if scenario == "invalid-base" else base]
    if scenario == "changed-override":
        args += ["--changed", ".github/workflows/ci.yml", "tests/test_ci_workflow.py"]
    assert smoke.main(args) == (0 if scenario == "exact" else 1)
    if scenario == "exact":
        assert output.read_text(encoding="utf-8").splitlines() == sorted(smoke.BACKBONE)
    else:
        assert not output.exists()
