#!/usr/bin/env python3
"""Assign every backend test file once, weighted by actual pytest collection count."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def discover(root: Path = ROOT) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix() for p in root.glob("tests/**/test_*.py") if p.is_file()
    )


def collected_weights(root: Path = ROOT) -> dict[str, int]:
    """Collect, never execute; errors are fatal rather than a smaller passing suite."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--color=no", "tests"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    counts: Counter[str] = Counter()
    for line in result.stdout.splitlines():
        if re.match(r"^tests[/\\].*\.py::", line):
            counts[line.split("::", 1)[0].replace("\\", "/")] += 1
    total = re.search(r"(\d+) tests? collected", result.stdout)
    if not total or int(total[1]) != sum(counts.values()) or not counts:
        raise ValueError("Cannot verify complete pytest collection; refusing shard assignment")
    files = discover(root)
    if set(counts) - set(files):
        raise ValueError("Collected tests outside the discovered test-file set")
    # Empty test files still belong to Full, and receive a minimal scheduling weight.
    return {path: max(1, counts[path]) for path in files}


def assign(weights: dict[str, int], count: int) -> list[list[str]]:
    if count < 1 or count > len(weights) or any(weight < 1 for weight in weights.values()):
        raise ValueError("Shard count must be positive and no greater than the test-file count")
    shards: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    for path in sorted(weights, key=lambda p: (-weights[p], p)):
        target = min(range(count), key=lambda index: (loads[index], index))
        shards[target].append(path)
        loads[target] += weights[path]
    for shard in shards:
        shard.sort()
    validate(shards, list(weights))
    return shards


def validate(shards: list[list[str]], files: list[str]) -> None:
    flattened = [path for shard in shards for path in shard]
    if (
        not shards
        or any(not shard for shard in shards)
        or len(flattened) != len(set(flattened))
        or set(flattened) != set(files)
    ):
        raise ValueError("Full assignment must be nonempty, complete and disjoint")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, help="One-based shard number; omit to validate all")
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--out", help="Write one assigned test file per line")
    args = parser.parse_args(argv)
    if args.shard is not None and not 1 <= args.shard <= args.count:
        parser.error("--shard must be between 1 and --count")
    if args.out and args.shard is None:
        parser.error("--out requires --shard")
    try:
        weights = collected_weights()
        shards = assign(weights, args.count)
        validate(shards, discover())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Full shard assignment refused: {error}", file=sys.stderr)
        return 1
    for index, paths in enumerate(shards, 1):
        print(
            f"Shard {index}/{args.count}: {len(paths)} files, "
            f"{sum(weights[p] for p in paths)} collected-test weight"
        )
    print(
        f"Coverage: all {len(weights)} test files assigned exactly once. Counts are not durations."
    )
    if args.out:
        Path(args.out).write_text("\n".join(shards[args.shard - 1]) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
