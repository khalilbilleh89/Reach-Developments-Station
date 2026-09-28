"""The legacy integration smoke selector remains deterministic and guarded."""

from __future__ import annotations

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


def test_every_existing_module_is_owned_or_explicitly_system_risk() -> None:
    domains = {
        path.name
        for path in (ROOT / "app/modules").iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    assert domains <= set(smoke.DOMAIN_SMOKE) | {"access"}


@pytest.mark.parametrize("domain", sorted(smoke.DOMAIN_SMOKE))
def test_smoke_contracts_remain_direct(domain: str) -> None:
    nodes, domains = smoke.select([f"app/modules/{domain}/service.py"])
    assert domains == [domain]
    assert set(nodes) == set(smoke.BACKBONE) | set(smoke.DOMAIN_SMOKE[domain])


@pytest.mark.parametrize(
    "path",
    [
        "app/core/config.py",
        "app/modules/access/service.py",
        "tests/conftest.py",
        "requirements.txt",
        "app/db/base.py",
        "app/db/migrations/env.py",
        ".github/workflows/ci.yml",
    ],
)
def test_smoke_refuses_system_risk_instead_of_silently_narrowing(path: str) -> None:
    with pytest.raises(smoke.SmokeRefused, match=r"full-gate|blast radius"):
        smoke.select([path])


def test_new_domain_refuses_until_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(smoke.DOMAIN_SMOKE, "commissions")
    with pytest.raises(smoke.SmokeRefused, match=r"commissions.*no Backend Smoke contract"):
        smoke.select(["app/modules/commissions/service.py"])


def test_unclassified_migration_refuses() -> None:
    with pytest.raises(smoke.SmokeRefused, match="Unclassified migration"):
        smoke.select(["app/db/migrations/versions/0099_projects_example.py"])


def test_smoke_cli_failure_is_nonzero_and_writes_nothing(tmp_path: Path) -> None:
    output = tmp_path / "selected.txt"
    assert smoke.main(["--changed", "app/core/database.py", "--out", str(output)]) == 1
    assert not output.exists()


def test_required_ci_no_longer_routes_by_smoke_or_review_readiness() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "ci_backend_smoke.py" not in workflow
    assert "github.event.pull_request.draft" not in workflow
    assert "ci_backend_tests.py" in workflow
