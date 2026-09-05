"""Guards on the shape of the CI workflow itself.

The workflow decides what proof this repository has of its own soundness, and
nothing else checks it. PR #251 is the case that made this file necessary: it
was marked ready for review and merged thirty-three seconds later, so the full
suite's test step began *after* the merge had landed. Everything about that was
legal — the workflow ran what it was told to, the reviewer merged a pull request
whose checks had started — and the result was a commit on ``main`` that no run
had ever reported on.

These are pure text and structure assertions. Nothing here starts a process,
reads a database or calls GitHub, so the file costs nothing and belongs in the
always-run set beside the selector's own tests.

The evaluation semantics of an ``if:`` expression belong to GitHub, and nothing
here pretends to reimplement them. What is asserted instead are the structural
facts that make the intended behaviour possible: that the fast job cannot fire
outside a pull request, that the full job can fire on a push to ``main``, that
the two draft comparisons stay complementary, and that no job may run without a
bound on how long it runs for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

#: Every job the workflow defines. Named rather than discovered, so deleting a
#: job is a failing test rather than a silently shorter loop.
JOBS = ("backend_fast", "backend", "frontend")


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


# --------------------------------------------------------------------------- #
# What triggers a run
# --------------------------------------------------------------------------- #


def test_a_commit_reaching_main_is_tested() -> None:
    """Without this trigger main's health is nobody's measurement.

    Pre-merge CI answers "may this merge?" and binds only while somebody waits
    for it. A release is cut from main, so main needs an answer that does not
    depend on anybody's patience.
    """
    assert re.search(r"^  push:\n    branches: \[main\]$", source(), re.MULTILINE)


def test_the_pull_request_trigger_is_not_traded_away_for_it() -> None:
    """Post-merge CI reports; it does not gate. Both triggers or neither."""
    assert re.search(r"^  pull_request:\n    branches: \[main\]$", source(), re.MULTILINE)
    for event in ("ready_for_review", "converted_to_draft", "synchronize"):
        assert f"- {event}" in source(), event


def test_a_main_run_is_never_cancelled_by_the_next_merge() -> None:
    """A superseded pull request run is waste; a superseded main run is evidence.

    Each merged commit is the only commit that will ever be tested as itself.
    """
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in source()


# --------------------------------------------------------------------------- #
# Which backend job answers for which event
# --------------------------------------------------------------------------- #


def test_the_fast_job_cannot_fire_outside_a_pull_request() -> None:
    """A push carries no pull request, so a draft check alone decides by accident.

    Actions coerces a missing value to a number before comparing, which makes
    ``null == true`` false and ``null == false`` *true*. The full job would
    therefore have selected itself on a push either way — on arithmetic rather
    than on intent. Both jobs name the event instead.
    """
    condition = setting("backend_fast", "if")
    assert condition is not None
    assert "github.event_name == 'pull_request'" in condition


def test_the_full_job_answers_for_a_push_to_main() -> None:
    condition = setting("backend", "if")
    assert condition is not None
    assert "github.event_name == 'push'" in condition


def test_the_two_pull_request_conditions_stay_complementary() -> None:
    """Exactly one backend job per pull request event — never none, never both."""
    assert "github.event.pull_request.draft == true" in (setting("backend_fast", "if") or "")
    assert "github.event.pull_request.draft == false" in (setting("backend", "if") or "")


def test_the_full_job_runs_the_whole_suite_unfiltered() -> None:
    """A full run that quietly excluded something would be worse than no run."""
    assert re.search(r"^        run: pytest -q --durations=20$", block("backend"), re.MULTILINE)


# --------------------------------------------------------------------------- #
# How long a job may take before it is a failure
# --------------------------------------------------------------------------- #


def test_the_fast_job_is_bounded_for_its_worst_case_not_its_usual_one() -> None:
    """Fast names a selection, not a promise about duration.

    An unrecognised change — a new module, a shared fixture, ``app/core/`` —
    deliberately falls back to ``pytest -q tests``, so the fast job's worst case
    is the entire suite. A bound set from the usual targeted run would kill
    exactly the fallback runs the fallback exists for.
    """
    fast = setting("backend_fast", "timeout-minutes")
    full = setting("backend", "timeout-minutes")
    assert fast is not None and full is not None
    assert int(fast) >= int(full)


@pytest.mark.parametrize("job", JOBS)
def test_every_job_is_bounded(job: str) -> None:
    """Actions defaults to six hours, which is not a timeout, it is a weekend.

    An unbounded job that hangs reports nothing and costs everything; a bounded
    one fails, which is at least an answer somebody can act on.
    """
    limit = setting(job, "timeout-minutes")
    assert limit is not None, f"{job} has no timeout-minutes"
    assert 0 < int(limit) <= 120, f"{job} bound is {limit} minutes"
