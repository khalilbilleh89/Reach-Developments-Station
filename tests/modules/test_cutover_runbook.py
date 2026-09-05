"""The runbook is checked against the tool, because a stale runbook is followed.

Every other guard on this branch compares a document against itself, and five of
them turned out vacuous for exactly that reason. This file is the opposite by
construction: nothing here reads the runbook twice. Every assertion takes a
claim out of the prose and puts it next to the thing it describes — the CLI's
exit codes, its registered actions, its flags, the check names it emits, the
ignore rules.

The failure being prevented is specific. Somebody renames a check, or adds an
exit code, or registers ``apply``; the runbook still reads plausibly, and the
person on shift at two in the morning follows it into a state nobody designed.
A document that has drifted from its tool is worse than no document.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from scripts.migration.__main__ import ACTIONS, EXIT_BLOCKED, EXIT_UNRECORDED, build_parser

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs/go_live/RUNBOOK.md"
GATE = REPO_ROOT / "docs/go_live/README.md"

#: The exit-code table: ``0   the action passed — ...``
_EXIT_ROW = re.compile(r"^(\d)\s{2,}(.+)$", re.MULTILINE)
#: A shell block's invocation and the flags it shows.
_INVOCATION = re.compile(r"python -m scripts\.migration(?: --json)? ([a-z-]+)")
_FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)")
#: A check name in the refusal table: ``| `source_unchanged` FAIL | ...``
_CHECK_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s+FAIL\s*\|", re.MULTILINE)


def runbook() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def emitted_checks() -> set[str]:
    """Every check name the CLI can put in a report, read from the source.

    Both halves: the source-side ones are ``record("name", ...)`` in the entry
    point, the target-side ones ``_check("name", ...)`` in ``target.py``.
    """
    entry = (REPO_ROOT / "scripts/migration/__main__.py").read_text(encoding="utf-8")
    target = (REPO_ROOT / "scripts/migration/target.py").read_text(encoding="utf-8")
    return set(re.findall(r'record\(\s*\n?\s*"([a-z_]+)"', entry)) | set(
        re.findall(r'_check\(\s*\n?\s*"([a-z_]+)"', target)
    )


# --------------------------------------------------------------------------- #
# The operational contract
# --------------------------------------------------------------------------- #


def test_the_exit_codes_are_the_ones_the_tool_returns() -> None:
    """A script branches on these, so a wrong table is a wrong branch.

    The values are compared against the module's own constants rather than
    against a list repeated here, which would be a third copy of the same claim.
    """
    documented = {int(code) for code, _ in _EXIT_ROW.findall(runbook())}
    assert documented == {0, EXIT_BLOCKED, 2, EXIT_UNRECORDED}


def test_every_command_shown_names_a_registered_action() -> None:
    """An action that was renamed leaves a runbook telling somebody to type it."""
    shown = set(_INVOCATION.findall(runbook()))
    assert shown, "the runbook shows no command at all"
    registered = {action.name for action in ACTIONS}
    assert shown <= registered, f"the runbook shows unregistered action(s): {shown - registered}"


def test_every_flag_shown_exists_on_the_parser() -> None:
    """Including the ones in prose, not only the ones in the code block."""
    parser = build_parser()
    subcommands = {a.dest: a for a in parser._subparsers._group_actions}["action"]
    real = {option for action in parser._actions for option in action.option_strings}
    for name in {action.name for action in ACTIONS}:
        real.update(
            option
            for action in subcommands.choices[name]._actions
            for option in action.option_strings
        )

    shown = set(_FLAG.findall(runbook()))
    assert shown, "the runbook shows no flags"
    assert shown <= real, (
        f"the runbook shows flag(s) the tool does not have: {sorted(shown - real)}"
    )


def test_the_required_flags_are_documented_as_required() -> None:
    """The sentence that stops somebody reading exit 2 as a blocked batch."""
    text = runbook()
    assert "`--bundle` and `--manifest` are **required**" in text
    assert "exits `2`" in text


# --------------------------------------------------------------------------- #
# Every refusal it explains is one the tool can produce
# --------------------------------------------------------------------------- #


def test_every_check_the_runbook_explains_is_one_the_tool_emits() -> None:
    """A row for a check that no longer exists is advice about nothing."""
    explained = set(_CHECK_ROW.findall(runbook()))
    assert explained, "the runbook explains no checks"
    emitted = emitted_checks()
    assert explained <= emitted, f"explained but never emitted: {sorted(explained - emitted)}"


def test_every_check_the_tool_emits_is_explained() -> None:
    """The direction that matters more.

    An operator meeting an unexplained refusal at two in the morning has to read
    the source to find out what it means, and will instead guess. A new check
    fails this until somebody writes the row.
    """
    explained = set(_CHECK_ROW.findall(runbook()))
    missing = sorted(emitted_checks() - explained)
    assert not missing, (
        f"the tool can refuse with {missing} and the runbook does not say what to do"
    )


def test_the_incomplete_result_is_explained() -> None:
    """The word that exists to stop a source-only run reading as a pass."""
    text = runbook()
    assert "`INCOMPLETE`, not `PASS`" in text
    assert "Do not proceed on this result." in text


# --------------------------------------------------------------------------- #
# It does not describe things that do not exist
# --------------------------------------------------------------------------- #


def test_the_runbook_says_apply_does_not_exist_and_it_does_not() -> None:
    """Two claims that have to move together.

    The day ``apply`` is registered, this fails — and it should, because the
    runbook then contains a paragraph telling an operator it is unavailable, and
    a section on what to do when a batch goes wrong that assumes nobody can have
    applied one.
    """
    assert "apply" not in {action.name for action in ACTIONS}
    assert "`apply` does not exist." in runbook()
    assert "**`apply`** | **DOES NOT EXIST.**" in GATE.read_text(encoding="utf-8")


def test_the_gate_does_not_claim_any_blocked_thing_is_ready() -> None:
    """Go-live is a decision somebody signs. Nothing here reports it."""
    text = GATE.read_text(encoding="utf-8")
    assert "**Status: NO-GO.**" in text
    assert "**None of these is met.**" in text
    assert "not a trial migration" in text


def test_the_working_directory_the_runbook_names_is_actually_ignored() -> None:
    """The one instruction whose failure leaks the client's data into a history."""
    assert "**`migration-work/`**" in runbook()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "migration-work/manifest.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert ignored.returncode == 0, "the runbook sends the client's data somewhere git would keep"


@pytest.mark.parametrize("document", [RUNBOOK, GATE])
def test_the_documents_exist_and_are_not_placeholders(document: Path) -> None:
    assert document.is_file()
    assert len(document.read_text(encoding="utf-8").splitlines()) > 40
