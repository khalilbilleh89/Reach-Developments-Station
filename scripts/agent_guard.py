"""Deterministic guards a coding agent's tool calls are checked against.

The rules here are the repository's, not one agent's: an agent never merges,
never rewrites shared history, never edits on ``main`` and never writes a local
secret file. `.claude/settings.json` is only the adapter that tells Claude Code
when to run them, so any other agent — or a human — can reach the same
decisions by calling this module.

Everything is a pure function over a string or a path. Nothing here executes a
command it was given, interpolates hook input into a shell, or reads a file the
agent named: the input arrives from a tool call and is treated as hostile.

Exit codes follow the hook contract: ``0`` allows, ``2`` blocks. A deny also
prints the hook's JSON so the reason reaches the agent rather than a bare
refusal it will retry.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: The branch nothing may be pushed to, merged into, or edited while on.
PROTECTED_BRANCH = "main"

#: Local secret files. `.env.example` is tracked on purpose and is not one.
SECRET_FILENAMES = frozenset(
    {".env", ".env.local", ".env.production", ".env.development", ".env.test"}
)


@dataclass(frozen=True)
class Decision:
    """Whether a tool call may proceed, and why not when it may not."""

    allowed: bool
    reason: str = ""

    @property
    def denied(self) -> bool:
        return not self.allowed


ALLOW = Decision(allowed=True)


def _words(command: str) -> list[str]:
    """The command as argument words, with shell punctuation dropped.

    ``shlex`` understands quoting, so ``rm -rf "a b"`` is three words rather
    than four, and a quoted flag cannot smuggle itself past a substring scan.
    An unbalanced quote is not a reason to allow the command: the raw split is
    used instead, which can only ever see more words, never fewer.
    """

    try:
        return shlex.split(command, comments=True)
    except ValueError:
        return command.split()


def _segments(command: str) -> list[list[str]]:
    """Each separately executed command in a compound line.

    ``git status && git push --force`` is two commands, and only scanning the
    first is how a guard gets walked past.
    """

    separators = {"&&", "||", ";", "|", "&", "\n"}
    segments: list[list[str]] = [[]]
    for word in _words(command.replace("\n", " \n ")):
        if word in separators:
            segments.append([])
        else:
            segments[-1].append(word)
    return [segment for segment in segments if segment]


def _flag_letters(words: list[str]) -> set[str]:
    """Every short flag letter given, so ``-rf``, ``-fr`` and ``-r -f`` agree."""

    letters: set[str] = set()
    for word in words:
        if word.startswith("-") and not word.startswith("--"):
            letters.update(word[1:])
    return letters


def _has(words: list[str], *long_flags: str) -> bool:
    return any(word in long_flags for word in words)


def _is(segment: list[str], *program: str) -> bool:
    """Whether the segment invokes this program, ignoring a leading ``sudo``."""

    words = segment[1:] if segment and segment[0] == "sudo" else segment
    if len(words) < len(program):
        return False
    return [word.lower() for word in words[: len(program)]] == list(program)


def _git_subcommand(segment: list[str], subcommand: str) -> list[str] | None:
    """The arguments of ``git <subcommand>``, or None when that is not this."""

    words = segment[1:] if segment and segment[0] == "sudo" else segment
    if not words or words[0].lower() != "git":
        return None
    # `git -C path push` — skip the options that precede the subcommand.
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in {"-C", "-c", "--git-dir", "--work-tree"} else 1
    if index >= len(words) or words[index].lower() != subcommand:
        return None
    return words[index + 1 :]


def _refspecs(arguments: list[str]) -> list[str]:
    """The refspecs of a ``git push``, with the remote and the flags removed."""

    positional = [argument for argument in arguments if not argument.startswith("-")]
    return positional[1:]


def _forces_by_refspec(arguments: list[str]) -> bool:
    """Whether a refspec forces the push with a leading ``+``.

    ``git push origin +main`` is a force push written without ``--force``, and
    a guard that only reads the flags waves it through.
    """

    return any(refspec.startswith("+") for refspec in _refspecs(arguments))


def _pushes_to_protected(arguments: list[str], current_branch: str | None) -> bool:
    """Whether this ``git push`` would land on the protected branch.

    A refspec names its destination after the colon when it has one, so
    ``HEAD:main`` and ``feature:main`` are both a push to main. With no refspec
    at all the push follows the current branch, which is why the branch is
    consulted rather than assumed.
    """

    refspecs = _refspecs(arguments)
    if not refspecs:
        return current_branch == PROTECTED_BRANCH
    for refspec in refspecs:
        destination = refspec.lstrip("+").split(":")[-1]
        if destination.rsplit("/", 1)[-1] == PROTECTED_BRANCH:
            return True
    return False


def check_shell_command(command: str, current_branch: str | None = None) -> Decision:
    """Whether a shell command an agent proposed may run."""

    for segment in _segments(command):
        decision = _check_segment(segment, current_branch)
        if decision.denied:
            return decision
    return ALLOW


def _check_segment(segment: list[str], current_branch: str | None) -> Decision:
    letters = _flag_letters(segment)

    recursive_rm = _is(segment, "rm") and ("r" in letters or _has(segment, "--recursive", "-R"))
    if recursive_rm and ("f" in letters or _has(segment, "--force")):
        return Decision(
            False,
            "`rm -rf` is blocked. Delete a named path without the recursive "
            "force flags, or ask the user to run it themselves.",
        )

    if _is(segment, "remove-item") or _is(segment, "ri"):
        recursive = _has(segment, "-Recurse", "-recurse", "-r")
        forced = _has(segment, "-Force", "-force")
        if recursive and forced:
            return Decision(
                False,
                "`Remove-Item -Recurse -Force` is blocked. Remove a named path "
                "without recursive force.",
            )

    reset = _git_subcommand(segment, "reset")
    if reset is not None and _has(reset, "--hard"):
        return Decision(
            False,
            "`git reset --hard` discards uncommitted work. Use `git stash` or "
            "`git restore <path>`, or ask the user first.",
        )

    clean = _git_subcommand(segment, "clean")
    if clean is not None:
        clean_letters = _flag_letters(clean)
        if "f" in clean_letters or _has(clean, "--force"):
            return Decision(
                False,
                "`git clean -fd` deletes untracked files that were never saved "
                "anywhere. Remove the specific files you meant instead.",
            )

    push = _git_subcommand(segment, "push")
    if push is not None:
        if _has(push, "--force", "-f") or _forces_by_refspec(push):
            return Decision(
                False,
                "`git push --force` rewrites history others may have pulled. "
                "Use `--force-with-lease` when a rewrite is genuinely intended.",
            )
        if _pushes_to_protected(push, current_branch):
            return Decision(
                False,
                f"Pushing to `{PROTECTED_BRANCH}` is blocked. Push the feature "
                "branch and open a pull request; a human merges it.",
            )

    if _is(segment, "gh", "pr", "merge"):
        return Decision(
            False,
            "Agents do not merge pull requests. Leave the pull request for a "
            "human to merge (AGENTS.md, CLAUDE.md).",
        )

    return ALLOW


def check_merge_tool(tool_name: str) -> Decision:
    """Whether an API tool call that would merge a pull request may run.

    `gh` is absent from several of the environments this repository is worked
    in, so blocking only the CLI would leave the rule true on paper and
    unenforced in practice.
    """

    if re.search(r"merge_pull_request|pull_request_merge", tool_name):
        return Decision(
            False,
            "Agents do not merge pull requests. Leave the pull request for a "
            "human to merge (AGENTS.md, CLAUDE.md).",
        )
    return ALLOW


def _relative_to_repository(file_path: str, repository_root: Path) -> Path | None:
    """The path inside the repository, or None when it points outside it.

    Claude supplies absolute paths, and Windows spells them with backslashes,
    so both separators are normalised before the comparison. A path that
    resolves outside the project — a scratchpad file, a temporary directory —
    is not the repository's business and is left alone.
    """

    try:
        candidate = Path(file_path.replace("\\", "/"))
        if not candidate.is_absolute():
            candidate = repository_root / candidate
        return candidate.resolve().relative_to(repository_root.resolve())
    except (ValueError, OSError):
        return None


def check_write(file_path: str, repository_root: Path, current_branch: str | None) -> Decision:
    """Whether an agent may create or modify this file."""

    relative = _relative_to_repository(file_path, repository_root)
    if relative is None:
        return ALLOW

    name = relative.name
    if name in SECRET_FILENAMES or (
        name.startswith(".env.") and not name.endswith((".example", ".sample", ".template"))
    ):
        return Decision(
            False,
            f"`{relative.as_posix()}` holds local secrets and is never written "
            "by an agent. Document the variable in `.env.example` instead.",
        )

    if current_branch == PROTECTED_BRANCH:
        return Decision(
            False,
            f"Direct repository edits on `{PROTECTED_BRANCH}` are blocked. "
            "Create or switch to a feature branch first, then retry the edit.",
        )

    return ALLOW


def current_git_branch(repository_root: Path) -> str | None:
    """The checked-out branch, or None when git cannot say.

    A detached HEAD and a missing git are both "not on the protected branch":
    the guard refuses tool calls, and a guard that cannot read the branch must
    not refuse every edit in the repository because of it.
    """

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    branch = completed.stdout.strip()
    return branch if completed.returncode == 0 and branch and branch != "HEAD" else None


def _deny(reason: str) -> int:
    """Print the hook's refusal and block the call."""

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    print(reason, file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Unreadable hook input is not evidence of a dangerous command, and a
        # guard that fails closed here would block every tool call.
        return 0
    if not isinstance(event, dict):
        return 0

    tool_input = event.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    repository_root = Path(__file__).resolve().parent.parent
    branch = current_git_branch(repository_root)

    if mode == "shell":
        tool_name = str(event.get("tool_name", ""))
        decision = check_merge_tool(tool_name)
        if decision.denied:
            return _deny(decision.reason)
        command = tool_input.get("command")
        if isinstance(command, str) and command.strip():
            decision = check_shell_command(command, branch)
            if decision.denied:
                return _deny(decision.reason)
        return 0

    if mode == "write":
        file_path = tool_input.get("file_path")
        if isinstance(file_path, str) and file_path:
            decision = check_write(file_path, repository_root, branch)
            if decision.denied:
                return _deny(decision.reason)
        return 0

    print(f"agent_guard.py: unknown mode {mode!r}; expected 'shell' or 'write'", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover - exercised through the hook
    raise SystemExit(main(sys.argv))
