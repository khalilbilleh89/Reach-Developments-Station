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


def condition(job: str, event: str, base: str, draft: bool, ui_only: bool = False) -> bool:
    expression = setting(job, "if")
    if expression is None:
        return True
    values = {
        "needs.development_scope.outputs.frontend_only": repr("true" if ui_only else "false"),
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
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], ast.Eq):
                return read(node.left) == read(node.comparators[0])
            if isinstance(node.ops[0], ast.NotEq):
                return read(node.left) != read(node.comparators[0])
        raise AssertionError(f"Unhandled workflow expression: {ast.dump(node)}")

    return bool(read(tree.body))


@pytest.mark.parametrize(
    ("event", "base", "draft", "expected"),
    [
        ("pull_request", "integration/mvp3", True, {"backend_smoke", "frontend"}),
        ("pull_request", "integration/mvp3", False, {"backend_smoke", "frontend"}),
        ("pull_request", "integration/mvp3-management", True, {"backend_smoke", "frontend"}),
        ("pull_request", "integration/mvp3-management", False, {"backend_smoke", "frontend"}),
        ("pull_request", "main", True, {"backend_fast", "frontend"}),
        ("pull_request", "main", False, {"backend_static", "backend_full", "backend", "frontend"}),
        ("push", "", False, {"backend_static", "backend_full", "backend", "frontend"}),
        ("pull_request", "unrelated", False, {"frontend"}),
    ],
)
def test_lane_routing(event: str, base: str, draft: bool, expected: set[str]) -> None:
    assert {job for job in JOBS if condition(job, event, base, draft)} == expected


@pytest.mark.parametrize("draft", (True, False))
def test_approved_ui_delivery_skips_backend_entry_and_aggregator(draft: bool) -> None:
    for job in ("backend_fast", "backend_static", "backend"):
        assert not condition(job, "pull_request", "main", draft, ui_only=True)
    # Full remains dependent on successful structural checks, so a skipped
    # structural job cannot start database shards.
    needs = setting("backend_full", "needs") or ""
    assert "backend_static" in needs and "development_scope" in needs
    assert "always()" not in (setting("backend_full", "if") or "")
    assert condition("frontend", "pull_request", "main", draft, ui_only=True)


def test_main_health_and_integration_triggers() -> None:
    assert re.search(r"^  push:\n    branches: \[main\]$", source(), re.MULTILINE)
    assert "branches: [main, integration/mvp3, integration/mvp3-management]" in source()
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
    assert "backend_static" in (setting("backend_full", "needs") or "")
    assert "fail-fast: false" in content
    # The matrix and the shard command read the same output, so Full cannot be
    # widened in one place and left narrow in the other — the failure that
    # would silently drop a quarter of the suite on the floor.
    assert "shard: ${{ fromJSON(needs.development_scope.outputs.shards) }}" in content
    assert "image: postgres:16" in content
    assert "alembic upgrade head" in content
    assert (
        "ci_backend_shards.py --shard ${{ matrix.shard }} "
        "--count ${{ needs.development_scope.outputs.shard_count }} --out selected-tests.txt"
        in content
    )
    assert "--scope ${{ needs.development_scope.outputs.full_scope || 'all' }}" in content
    assert "pytest -q $(tr '\\n' ' ' < selected-tests.txt) --durations=20" in content
    assert "--maxfail" not in content
    assert "--ignore" not in content
    assert "continue-on-error" not in source()
    assert (
        "ci_backend_shards.py --count ${{ needs.development_scope.outputs.shard_count }}"
        in block("backend_static")
    )


def test_the_shard_width_is_decided_in_exactly_one_place() -> None:
    """Four literals and three assertions used to agree by hand.

    Full's width was the number 4 written into the matrix, the shard command,
    the validating command and the job name, with tests pinning three of them.
    Widening it meant changing six things in step; getting it half right would
    have run six shards of an eight-way split and quietly skipped the rest.
    """
    scope = block("development_scope")
    assert "SHARD_COUNT:" in scope, "nothing in development_scope decides the width"
    assert "shards: ${{ steps.width.outputs.shards }}" in source()
    assert "shard_count: ${{ steps.width.outputs.shard_count }}" in source()

    # No survivor of the old hand-written width anywhere in the workflow.
    for stale in ("shard: [1, 2, 3, 4]", "--count 4", "Full ${{ matrix.shard }}/4"):
        assert stale not in source(), f"a hardcoded shard width survives: {stale}"


def test_full_is_wide_enough_to_be_worth_sharding_and_not_so_wide_it_queues() -> None:
    """Width is a judgement, so the judgement is written down and checked.

    This account runs at most twenty concurrent jobs. A run is the shards plus
    about four other jobs, and a pull request run regularly overlaps a push to
    main, so anything past ten shards spends its gain sitting in a queue.
    """
    width = int(re.search(r"SHARD_COUNT:\s*(\d+)", block("development_scope"))[1])
    assert 4 <= width <= 10, (
        f"Full runs {width} ways. Below four is barely sharded; above ten, two "
        "overlapping runs exceed the concurrent-job limit and queue."
    )
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
    assert "needs: [development_scope, backend_static, backend_full]" in content
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


# --------------------------------------------------------------------------- #
# Narrowing Full to the guards a frontend change can reach
# --------------------------------------------------------------------------- #

SCOPE_SCRIPT = ROOT / "scripts" / "ci_development_ui.mjs"
REPOSITORY = "khalilbilleh89/Reach-Developments-Station"


def scoped(event: dict, paths: list[str]) -> bool:
    """Ask the real module, so this cannot drift from what CI actually runs."""
    program = (
        f"import {{ isFrontendScoped }} from {str(SCOPE_SCRIPT.as_uri())!r};"
        f"process.stdout.write(String(isFrontendScoped({event!r}, {paths!r})));"
    ).replace("'", '"')
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == "true"


def pull_request(**over: str) -> dict:
    return {
        "name": "pull_request",
        "base": "main",
        "head": "claude/some-ui-change",
        "repository": REPOSITORY,
        "headRepository": REPOSITORY,
        **over,
    }


def test_a_diff_confined_to_the_frontend_scopes_full() -> None:
    assert scoped(pull_request(), ["frontend/src/app/globals.css", "frontend/tests/a.test.mjs"])


@pytest.mark.parametrize(
    "paths",
    (
        ["frontend/src/app/globals.css", "app/modules/inventory/service.py"],
        ["app/modules/inventory/service.py"],
        ["tests/test_product_experience.py"],
        [".github/workflows/ci.yml"],
        ["docs/ARCHITECTURE.md"],
        ["frontend/../app/main.py"],
    ),
)
def test_anything_outside_the_frontend_keeps_the_whole_suite(paths: list[str]) -> None:
    """One backend path in the diff is enough, and traversal is not a frontend path."""
    assert not scoped(pull_request(), paths)


def test_a_push_to_main_is_never_scoped() -> None:
    # The branch everything merges into always runs the complete suite. This is
    # the safety net that makes narrowing a pull request defensible at all.
    assert not scoped(pull_request(name="push"), ["frontend/src/app/globals.css"])


def test_a_fork_and_an_empty_diff_are_never_scoped() -> None:
    assert not scoped(pull_request(headRepository="someone/fork"), ["frontend/src/a.css"])
    assert not scoped(pull_request(base="integration/mvp3"), ["frontend/src/a.css"])
    # An empty set satisfies `every`, which would narrow Full to nothing.
    assert not scoped(pull_request(), [])


def test_the_workflow_passes_the_computed_scope_to_both_shard_commands() -> None:
    """A scope the workflow never reads is a policy that does not exist."""
    assert "full_scope: ${{ steps.scope.outputs.full_scope }}" in block("development_scope")
    for job in ("backend_static", "backend_full"):
        content = block(job)
        assert "ci_backend_shards.py" in content
        assert "--scope ${{ needs.development_scope.outputs.full_scope || 'all' }}" in content
        assert "development_scope" in setting(job, "needs") or ""
