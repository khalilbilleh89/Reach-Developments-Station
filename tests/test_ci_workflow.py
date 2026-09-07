"""Exercise actual workflow conditions and the fail-closed Full aggregator."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
JOBS = ("backend_smoke", "backend_fast", "backend_static", "backend_full", "backend", "frontend")


def source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def block(job: str) -> str:
    """The lines of one job's definition, up to the next job at the same indent.

    Two-space indentation under ``jobs:`` is the file's own convention and the
    only structure this needs; a real YAML parse would mean a new dependency to
    read six values.
    """
    text = source()
    start = text.index(f"\n  {job}:\n")
    rest = text[start + 1 :]
    following = re.search(r"\n  [a-z_]+:\n", rest)
    return rest[: following.start()] if following else rest


def setting(job: str, key: str) -> str | None:
    """One top-level ``key: value`` from a job, ignoring anything nested.

    A job's own keys sit at four spaces; anything deeper belongs to a service,
    a step or an env block and is not what a caller here is asking for.
    """
    found = re.search(rf"^    {re.escape(key)}: (.+)$", block(job), re.MULTILINE)
    return found.group(1).strip() if found else None


def condition(job: str, event: str, base: str, draft: bool) -> bool:
    expression = setting(job, "if")
    if expression is None:
        return True
    values = {
        "github.event_name": repr(event),
        "github.event.pull_request.base.ref": repr(base),
        "github.event.pull_request.draft": str(draft),
        "always()": "True",
        "true": "True",
        "false": "False",
    }
    for key, value in values.items():
        expression = expression.replace(key, value)
    tree = ast.parse(expression.replace("&&", "and").replace("||", "or"), mode="eval")

    def read(node: ast.AST) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            return (
                all(read(v) for v in node.values)
                if isinstance(node.op, ast.And)
                else any(read(v) for v in node.values)
            )
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
            return read(node.left) == read(node.comparators[0])
        raise AssertionError(f"Unhandled workflow expression: {ast.dump(node)}")

    return bool(read(tree.body))


@pytest.mark.parametrize(
    ("event", "base", "draft", "expected"),
    [
        ("pull_request", "integration/mvp3", True, {"backend_smoke", "frontend"}),
        ("pull_request", "integration/mvp3", False, {"backend_smoke", "frontend"}),
        ("pull_request", "main", True, {"backend_fast", "frontend"}),
        ("pull_request", "main", False, {"backend_static", "backend_full", "backend", "frontend"}),
        ("push", "", False, {"backend_static", "backend_full", "backend", "frontend"}),
        ("pull_request", "unrelated", False, {"frontend"}),
    ],
)
def test_lane_routing(event: str, base: str, draft: bool, expected: set[str]) -> None:
    assert {job for job in JOBS if condition(job, event, base, draft)} == expected


def test_main_health_and_integration_triggers() -> None:
    assert re.search(r"^  push:\n    branches: \[main\]$", source(), re.MULTILINE)
    assert "branches: [main, integration/mvp3]" in source()
    for event in (
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
        "converted_to_draft",
    ):
        assert event in source().split("permissions:")[0]
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in source()
    assert "github.event_name == 'pull_request' && github.ref || github.run_id" in source()
    assert "pull_request_target:" not in source()
    assert "contents: read" in source()


@pytest.mark.parametrize("job", JOBS)
def test_every_job_is_bounded(job: str) -> None:
    assert 0 < int(setting(job, "timeout-minutes") or "0") <= 240
    assert int(setting("backend_smoke", "timeout-minutes") or "0") == 30
    assert int(setting("backend_fast", "timeout-minutes") or "0") >= int(
        setting("backend_full", "timeout-minutes") or "0"
    )


@pytest.mark.parametrize("job", ("backend_smoke", "backend_fast", "backend_static"))
def test_real_postgres_and_structural_checks(job: str) -> None:
    content = block(job)
    for command in (
        "pip check",
        "ruff check .",
        "ruff format --check .",
        "python -m compileall app scripts",
        "alembic upgrade head",
        "alembic check",
    ):
        assert f"run: {command}" in content
    assert "image: postgres:16" in content
    assert "TZ: UTC" in content
    assert "--maxfail" not in content


def test_smoke_refuses_before_dependency_installation() -> None:
    content = block("backend_smoke")
    assert content.index("ci_backend_smoke.py") < content.index("Install dependencies")
    assert "pytest -q $(tr" in content
    assert "selected-smoke.txt" in content
    assert "ci_backend_tests.py" not in content


def test_shards_are_independent_complete_and_not_fail_fast() -> None:
    content = block("backend_full")
    assert "needs: backend_static" in content
    assert "fail-fast: false" in content
    assert "shard: [1, 2, 3, 4]" in content
    assert "image: postgres:16" in content
    assert "alembic upgrade head" in content
    assert (
        "ci_backend_shards.py --shard ${{ matrix.shard }} --count 4 --out selected-tests.txt"
        in content
    )
    assert "pytest -q $(tr '\\n' ' ' < selected-tests.txt) --durations=20" in content
    assert "--maxfail" not in content
    assert "--ignore" not in content
    assert "continue-on-error" not in source()
    assert "ci_backend_shards.py --count 4" in block("backend_static")
    assert all(
        path in block("backend_static")
        for path in (
            "test_ci_selector.py",
            "test_ci_workflow.py",
            "test_ci_smoke.py",
            "test_ci_shards.py",
        )
    )


@pytest.mark.parametrize("structural", ("success", "failure", "cancelled", "skipped"))
@pytest.mark.parametrize("shards", ("success", "failure", "cancelled", "skipped"))
def test_actual_aggregator_command_refuses_any_non_success(structural: str, shards: str) -> None:
    content = block("backend")
    assert setting("backend", "name") == "Backend"
    assert "needs: [backend_static, backend_full]" in content
    assert (setting("backend", "if") or "").startswith("always() &&")
    assert "needs.backend_static.result" in content and "needs.backend_full.result" in content
    command = re.search(r"run: python -c '(.+)'", content)
    assert command
    result = subprocess.run(
        [sys.executable, "-c", command[1]],
        env={**os.environ, "STRUCTURAL_RESULT": structural, "SHARDS_RESULT": shards},
        check=False,
    )
    assert (result.returncode == 0) == (structural == shards == "success")


def test_checks_use_reviewed_head_and_frontend_still_builds() -> None:
    for job in JOBS:
        if job != "backend":
            assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in block(job)
    assert "npm ci" in block("frontend")
    assert "npm run lint" in block("frontend")
    assert "npm run build" in block("frontend")
