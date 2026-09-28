"""Static contracts for risk-based required CI and optional Full shadow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
SHADOW = ROOT / ".github/workflows/full-backend-shadow.yml"


def source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def block(job: str, text: str | None = None) -> str:
    body = source() if text is None else text
    start = body.index(f"\n  {job}:\n")
    rest = body[start + 1 :]
    following = re.search(r"\n  [a-z_]+:\n", rest)
    return rest[: following.start()] if following else rest


def setting(job: str, key: str) -> str | None:
    found = re.search(rf"^    {re.escape(key)}: (.+)$", block(job), re.MULTILINE)
    return found.group(1).strip() if found else None


def test_required_status_names_are_preserved_exactly() -> None:
    assert setting("backend", "name") == "Backend"
    assert setting("frontend", "name") == "Frontend"
    quality = (ROOT / ".github/workflows/pr-quality.yml").read_text(encoding="utf-8-sig")
    assert "name: PR Quality" in quality


def test_draft_and_ready_events_use_the_same_plan() -> None:
    triggers = source().split("permissions:", 1)[0]
    assert "ready_for_review" in triggers
    assert "converted_to_draft" in triggers
    assert "github.event.pull_request.draft" not in source()
    assert "Backend Fast" not in source()
    assert "draft ==" not in source()


def test_ordinary_pr_uses_one_targeted_postgres_runner_not_eight_full_runners() -> None:
    targeted = block("backend_targeted")
    full = block("backend_system_full")
    assert "image: postgres:16" in targeted
    assert "timeout-minutes: 20" in targeted
    assert "full_required != 'true'" in targeted
    assert "full_required == 'true'" in full
    assert "matrix:" in full and "shard: [1, 2, 3, 4, 5, 6, 7, 8]" in full
    assert "backend_system_static.result == 'success'" in full


def test_targeted_job_keeps_static_migration_and_selected_test_safety() -> None:
    content = block("backend_targeted")
    for command in (
        "pip check",
        "ruff check .",
        "ruff format --check .",
        "python -m compileall app scripts",
        "alembic upgrade head",
        "alembic check",
        "pytest -q $(tr",
    ):
        assert command in content
    assert "selected-tests.txt" in content
    assert "--durations=20" in content
    assert "elapsed > 900" in content
    assert "timeout-minutes: 20" in content


def test_system_risk_can_still_require_complete_regression() -> None:
    static = block("backend_system_static")
    full = block("backend_system_full")
    assert "full_required == 'true'" in static
    assert "ci_backend_shards.py --count 8" in static
    assert "--shard ${{ matrix.shard }} --count 8" in full
    assert "pytest -q $(tr" in full
    assert "--ignore" not in full and "--maxfail" not in full
    assert "fail-fast: false" in full


def test_main_push_uses_the_actual_merged_diff_and_not_automatic_full() -> None:
    scope = block("scope")
    assert "github.event.pull_request.base.sha || github.event.before" in scope
    assert "github.event.pull_request.head.sha || github.sha" in scope
    assert 'ci_backend_tests.py --base "$DIFF_BASE" --head "$DIFF_HEAD"' in scope
    assert "github.event_name == 'push'" not in block("backend_system_full")


def test_backend_aggregate_always_exists_including_no_backend_changes() -> None:
    content = block("backend")
    assert setting("backend", "if") == "always()"
    assert "scope" in (setting("backend", "needs") or "")
    assert "No backend-affecting files changed — PASS" in content
    assert 'os.environ["BACKEND_REQUIRED"] != "true"' in content
    assert 'os.environ["FULL_REQUIRED"] == "true"' in content
    assert 'os.environ["TARGETED_RESULT"] == "success"' in content


def test_frontend_required_status_is_always_straightforward_and_complete() -> None:
    content = block("frontend")
    assert setting("frontend", "if") is None
    assert "npm ci" in content
    assert "npm run lint" in content
    assert "npm run build" in content
    package = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
    assert '"prebuild": "npm test"' in package


def test_same_pr_newer_run_cancels_older_run() -> None:
    assert "github.event.pull_request.number || github.run_id" in source()
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in source()
    assert "github.ref" not in source().split("jobs:", 1)[0]


@pytest.mark.parametrize(
    "job",
    [
        "scope",
        "backend_targeted",
        "backend_system_static",
        "backend_system_full",
        "backend",
        "frontend",
    ],
)
def test_every_required_workflow_job_is_bounded(job: str) -> None:
    timeout = int(setting(job, "timeout-minutes") or "0")
    assert 0 < timeout <= 40


def test_exact_head_is_checked_out_everywhere_code_runs() -> None:
    for job in (
        "scope",
        "backend_targeted",
        "backend_system_static",
        "backend_system_full",
        "frontend",
    ):
        assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in block(job)


def test_full_shadow_is_explicit_observable_and_not_required_backend() -> None:
    text = SHADOW.read_text(encoding="utf-8")
    assert "name: Full Backend Shadow" in text
    assert "workflow_dispatch:" in text
    assert "types: [labeled]" in text
    assert "github.event.label.name == 'ci:full'" in text
    assert text.count("github.event.label.name == 'ci:full'") == 2
    assert "--junitxml=" in text and "--durations=20" in text
    assert "pytest-" in text and "actions/upload-artifact@v4" in text
    for label in ("Total tests:", "Passed:", "Failed:", "Errors:", "Skipped:", "Slowest tests"):
        assert label in text
    assert "continue-on-error" not in text
    assert "Full Backend Shadow" not in block("backend")
    assert str(SHADOW.name) in (ROOT / "scripts/ci_backend_tests.py").read_text(encoding="utf-8")


def test_pr_quality_is_separate_and_description_edits_do_not_run_backend() -> None:
    quality = (ROOT / ".github/workflows/pr-quality.yml").read_text(encoding="utf-8-sig")
    assert "name: PR Quality" in quality
    assert "edited" in quality.split("permissions:", 1)[0]
    assert "edited" not in source().split("permissions:", 1)[0]
    assert "services:" not in quality
    assert "postgres" not in quality


def test_workflow_has_read_only_permissions_and_no_deployment() -> None:
    assert re.search(r"permissions:\n  contents: read\n", source())
    assert "pull_request_target:" not in source()
    assert ": write" not in source()
    assert "render" not in source().lower()
