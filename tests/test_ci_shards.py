"""Full coverage cannot depend on a human-maintained file list or shard count."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_backend_shards as shards  # noqa: E402


def test_discovery_includes_every_test_file_and_new_nested_files(tmp_path: Path) -> None:
    expected = sorted(
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*.py")
        if p.is_relative_to(ROOT / "tests") and p.name.startswith("test_")
    )
    assert shards.discover() == expected
    nested = tmp_path / "tests/new_domain/deeper/test_new.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("def test_new(): pass\n", encoding="utf-8")
    assert shards.discover(tmp_path) == ["tests/new_domain/deeper/test_new.py"]


@pytest.fixture(scope="module")
def weights() -> dict[str, int]:
    return shards.collected_weights()


@pytest.mark.parametrize("count", (1, 2, 4, 7))
def test_all_collected_files_exactly_once_for_any_count(
    weights: dict[str, int], count: int
) -> None:
    result = shards.assign(weights, count)
    assert len(result) == count and all(result)
    assert Counter(p for group in result for p in group) == Counter(shards.discover())
    assert result == shards.assign(dict(reversed(list(weights.items()))), count)
    assert all(group == sorted(group) for group in result)


def test_largest_first_balances_known_weights() -> None:
    assert shards.assign({"a": 10, "b": 9, "c": 2, "d": 1}, 2) == [["a", "d"], ["b", "c"]]


@pytest.mark.parametrize("count", (0, -1, 3))
def test_invalid_count_refuses(count: int) -> None:
    with pytest.raises(ValueError):
        shards.assign({"a": 1, "b": 1}, count)


@pytest.mark.parametrize(
    "assignment", ([["a"], ["a", "b"]], [["a"]], [["a", "b"], []], [["a", "b", "c"]])
)
def test_validation_rejects_omissions_duplicates_empty_or_extra(
    assignment: list[list[str]],
) -> None:
    with pytest.raises(ValueError):
        shards.validate(assignment, ["a", "b"])


def test_failed_collection_cannot_return_a_smaller_suite(tmp_path: Path) -> None:
    import subprocess

    with pytest.raises((subprocess.CalledProcessError, ValueError)):
        shards.collected_weights(tmp_path)


# --------------------------------------------------------------------------- #
# Scoping Full to the guards a frontend change can actually reach
# --------------------------------------------------------------------------- #


def test_the_frontend_scope_is_discovered_from_the_files_themselves(tmp_path: Path) -> None:
    """A guard added tomorrow joins the scope by reading the tree, not by a list.

    A hardcoded roster would rot into the failure this scope exists to avoid: a
    frontend pull request running no frontend guard at all, and passing.
    """
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_reads_frontend.py").write_text(
        "from pathlib import Path\n\n\ndef test_css():\n    Path('frontend/src/app/globals.css')\n",
        encoding="utf-8",
    )
    (tmp_path / "tests/test_backend_only.py").write_text(
        "def test_service():\n    assert True\n", encoding="utf-8"
    )

    assert shards.frontend_guards(tmp_path) == ["tests/test_reads_frontend.py"]


def test_the_real_frontend_scope_is_a_strict_and_useful_subset() -> None:
    guards, everything = shards.frontend_guards(), shards.discover()

    assert set(guards) < set(everything), "a scope that selects everything saves nothing"
    # The guards that caught real faults in frontend work. If a change ever drops
    # one of these from the scope, a frontend pull request stops being checked by
    # the suite that polices the frontend.
    for required in (
        "tests/test_product_experience.py",
        "tests/test_static_frontend.py",
        "tests/test_ux_copy.py",
    ):
        assert required in guards


@pytest.mark.parametrize("count", (1, 2, 4))
def test_a_scoped_full_still_assigns_its_population_exactly_once(
    weights: dict[str, int], count: int
) -> None:
    scoped = shards.population(weights, "frontend")
    result = shards.assign(scoped, count)

    assert Counter(p for group in result for p in group) == Counter(scoped.keys())
    assert set(scoped) == set(shards.frontend_guards())
    assert len(scoped) < len(weights)


def test_the_default_scope_is_every_file_and_an_unknown_scope_refuses(
    weights: dict[str, int],
) -> None:
    assert shards.population(weights, "all") == weights
    with pytest.raises(ValueError):
        shards.population(weights, "backend")


def test_a_scope_that_selects_nothing_refuses_rather_than_running_an_empty_full() -> None:
    # Full narrowing to nothing and reporting success is the one outcome that
    # would be worse than running the whole suite.
    with pytest.raises(ValueError):
        shards.population({"tests/test_service.py": 3}, "frontend", ROOT / "does-not-exist")
