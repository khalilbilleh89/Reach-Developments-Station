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
