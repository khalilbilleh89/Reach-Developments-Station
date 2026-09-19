"""The one lightweight check any agent or human runs before saying "done".

This is deliberately not the test suite. CI owns correctness; this catches the
cheap mistakes that otherwise reach a pull request and cost a review round — a
conflict marker left in a file, a settings file that no longer parses, a
tracked secret, formatter drift, a lint error.

Every check is scoped to what actually changed, so the command stays fast
enough to run without thinking about it. Tooling that is not installed is
reported as unavailable rather than silently passing: a check that cannot run
is not a check that passed.

    python scripts/agent_preflight.py           # report findings, exit 1 on any
    python scripts/agent_preflight.py --hook    # the same, as a Claude Stop hook

Exit codes: ``0`` clean, ``1`` findings to fix.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

#: Filenames that must never be tracked, whatever branch they appear on.
SECRET_FILENAMES = frozenset(
    {".env", ".env.local", ".env.production", ".env.development", ".env.test"}
)

#: Left in a file by an unfinished merge. Split so this file is not a match.
CONFLICT_MARKERS = ("<" * 7, "=" * 7, ">" * 7)

FRONTEND_SUFFIXES = (".ts", ".tsx", ".mjs", ".js", ".jsx")


@dataclass(frozen=True)
class Finding:
    """One actionable problem, or one check that could not be run."""

    check: str
    detail: str
    actionable: bool = True


def _run(command: list[str], cwd: Path = REPOSITORY_ROOT) -> subprocess.CompletedProcess[str]:
    """Run a command as an argument array — never through a shell."""

    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=180, check=False
    )


def changed_files(base: str = "origin/main") -> list[Path]:
    """Files this branch changes: committed against the base, plus the worktree.

    Falling back to the worktree alone when the base is unknown means a fresh
    clone or a detached checkout still gets checked, just more narrowly.
    """

    paths: set[str] = set()
    merge_base = _run(["git", "merge-base", "HEAD", base])
    if merge_base.returncode == 0 and merge_base.stdout.strip():
        committed = _run(["git", "diff", "--name-only", merge_base.stdout.strip()])
        if committed.returncode == 0:
            paths.update(committed.stdout.split())
    for arguments in (["diff", "--name-only"], ["diff", "--name-only", "--cached"]):
        result = _run(["git", *arguments])
        if result.returncode == 0:
            paths.update(result.stdout.split())
    untracked = _run(["git", "ls-files", "--others", "--exclude-standard"])
    if untracked.returncode == 0:
        paths.update(untracked.stdout.split())
    return sorted(REPOSITORY_ROOT / path for path in paths if path)


def check_whitespace() -> list[Finding]:
    """`git diff --check`: trailing whitespace and conflict markers git can see."""

    result = _run(["git", "diff", "--check"])
    if result.returncode == 0:
        return []
    return [Finding("whitespace", result.stdout.strip() or result.stderr.strip())]


def check_conflict_markers(paths: list[Path]) -> list[Finding]:
    """A merge marker left at the start of a line in a changed text file."""

    findings: list[Finding] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(content.splitlines(), start=1):
            if line.startswith(CONFLICT_MARKERS):
                findings.append(
                    Finding(
                        "conflict-markers",
                        f"{_relative(path)}:{number} still holds a merge conflict marker",
                    )
                )
                break
    return findings


def check_tracked_secrets() -> list[Finding]:
    """A local secret file that git has started tracking."""

    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        return [Finding("tracked-secrets", "git ls-files failed", actionable=False)]
    findings: list[Finding] = []
    for tracked in result.stdout.split():
        name = Path(tracked).name
        if name in SECRET_FILENAMES:
            findings.append(
                Finding(
                    "tracked-secrets",
                    f"{tracked} is tracked. Remove it with `git rm --cached` and "
                    "keep the variable names in `.env.example`.",
                )
            )
    return findings


def check_json(paths: list[Path]) -> list[Finding]:
    """Every changed JSON file still parses."""

    findings: list[Finding] = []
    for path in paths:
        if path.suffix != ".json" or not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
            findings.append(Finding("json", f"{_relative(path)} does not parse: {error}"))
    return findings


def check_python(paths: list[Path]) -> list[Finding]:
    """Ruff's lint and format verdicts on the changed Python files only."""

    python = [str(path) for path in paths if path.suffix == ".py" and path.is_file()]
    if not python:
        return []
    findings: list[Finding] = []
    for arguments, check in ((["check"], "ruff-check"), (["format", "--check"], "ruff-format")):
        try:
            result = _run([sys.executable, "-m", "ruff", *arguments, *python])
        except (OSError, subprocess.SubprocessError):
            findings.append(Finding(check, "ruff is not installed", actionable=False))
            continue
        if result.returncode != 0:
            findings.append(Finding(check, (result.stdout + result.stderr).strip()))
    return findings


def check_frontend(paths: list[Path]) -> list[Finding]:
    """ESLint on the changed frontend sources, using the repository's own copy.

    The project pins ESLint in `frontend/package.json`; a different version on
    the PATH reports different things, so only the installed binary is used and
    its absence is reported rather than worked around.
    """

    frontend_root = REPOSITORY_ROOT / "frontend"
    sources = [
        path
        for path in paths
        if path.suffix in FRONTEND_SUFFIXES and path.is_file() and _is_within(path, frontend_root)
    ]
    if not sources:
        return []
    binary = (
        frontend_root / "node_modules" / ".bin" / ("eslint.cmd" if os.name == "nt" else "eslint")
    )
    if not binary.exists():
        return [
            Finding(
                "eslint",
                "frontend/node_modules is not installed; run `npm install` in frontend/",
                actionable=False,
            )
        ]
    try:
        result = _run([str(binary), *[str(path) for path in sources]], cwd=frontend_root)
    except (OSError, subprocess.SubprocessError) as error:
        return [Finding("eslint", f"could not run eslint: {error}", actionable=False)]
    if result.returncode != 0:
        return [Finding("eslint", (result.stdout + result.stderr).strip())]
    return []


def check_claude_settings(paths: list[Path]) -> list[Finding]:
    """`.claude/settings.json` parses, is shaped like hooks, and its scripts exist."""

    settings_path = REPOSITORY_ROOT / ".claude" / "settings.json"
    if not any(path == settings_path for path in paths) or not settings_path.is_file():
        return []
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        return [Finding("claude-settings", f".claude/settings.json does not parse: {error}")]
    return validate_settings(settings)


def validate_settings(settings: object) -> list[Finding]:
    """Structural checks on a parsed settings document.

    Only what a typo would break is asserted: the shape Claude Code reads, and
    that every repository script a hook names is actually present. Anything
    stricter would fail the next time the hook schema gains a field.
    """

    findings: list[Finding] = []
    if not isinstance(settings, dict):
        return [Finding("claude-settings", "settings.json must be a JSON object")]
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return [Finding("claude-settings", "settings.json has no `hooks` object")]
    for event, handlers in hooks.items():
        if not isinstance(handlers, list):
            findings.append(Finding("claude-settings", f"hooks.{event} must be a list"))
            continue
        for handler in handlers:
            if not isinstance(handler, dict) or not isinstance(handler.get("hooks"), list):
                findings.append(
                    Finding("claude-settings", f"hooks.{event} entry has no `hooks` list")
                )
                continue
            for entry in handler["hooks"]:
                findings.extend(_check_handler_entry(event, entry))
    return findings


def _check_handler_entry(event: str, entry: object) -> list[Finding]:
    if not isinstance(entry, dict):
        return [Finding("claude-settings", f"hooks.{event} handler must be an object")]
    if entry.get("type") != "command":
        return [Finding("claude-settings", f"hooks.{event} handler must be type `command`")]
    if not entry.get("command"):
        return [Finding("claude-settings", f"hooks.{event} handler has no `command`")]
    findings: list[Finding] = []
    for argument in entry.get("args") or []:
        if not isinstance(argument, str) or "${CLAUDE_PROJECT_DIR}" not in argument:
            continue
        referenced = argument.replace("${CLAUDE_PROJECT_DIR}/", "")
        if not (REPOSITORY_ROOT / referenced).exists():
            findings.append(
                Finding("claude-settings", f"hooks.{event} refers to missing script {referenced}")
            )
    return findings


def check_skills(paths: list[Path]) -> list[Finding]:
    """A changed SKILL.md still has the frontmatter that makes it loadable."""

    findings: list[Finding] = []
    for path in paths:
        if path.name != "SKILL.md" or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            findings.append(Finding("skills", f"{_relative(path)} is unreadable: {error}"))
            continue
        if not lines or lines[0].strip() != "---":
            findings.append(Finding("skills", f"{_relative(path)} does not open with frontmatter"))
            continue
        try:
            closing = lines.index("---", 1)
        except ValueError:
            findings.append(Finding("skills", f"{_relative(path)} frontmatter is never closed"))
            continue
        frontmatter = lines[1:closing]
        for key in ("name:", "description:"):
            if not any(line.startswith(key) for line in frontmatter):
                findings.append(
                    Finding("skills", f"{_relative(path)} frontmatter has no `{key[:-1]}`")
                )
    return findings


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_preflight() -> list[Finding]:
    """Every check, against what this branch changed."""

    paths = changed_files()
    return [
        *check_whitespace(),
        *check_conflict_markers(paths),
        *check_tracked_secrets(),
        *check_json(paths),
        *check_claude_settings(paths),
        *check_skills(paths),
        *check_python(paths),
        *check_frontend(paths),
    ]


def format_report(findings: list[Finding]) -> str:
    """The findings as text an agent can act on without opening anything."""

    if not findings:
        return "Preflight: clean. CI remains the authority on correctness."
    actionable = [finding for finding in findings if finding.actionable]
    unavailable = [finding for finding in findings if not finding.actionable]
    lines: list[str] = []
    if actionable:
        lines.append(f"Preflight found {len(actionable)} problem(s) to fix before finishing:")
        lines.extend(f"  [{finding.check}] {finding.detail}" for finding in actionable)
    if unavailable:
        lines.append("Checks that could not run (not failures):")
        lines.extend(f"  [{finding.check}] {finding.detail}" for finding in unavailable)
    return "\n".join(lines)


def _already_reported(session_id: str, findings: list[Finding]) -> bool:
    """Whether this exact set of findings already blocked this session once.

    A Stop hook that blocks on findings the agent cannot fix would loop
    forever. Blocking once per distinct set of findings gives the agent its
    chance to act and then gets out of the way.
    """

    signature = hashlib.sha256(
        "\n".join(sorted(f"{f.check}:{f.detail}" for f in findings)).encode("utf-8")
    ).hexdigest()[:32]
    marker = Path(tempfile.gettempdir()) / f"reach-preflight-{session_id or 'local'}-{signature}"
    if marker.exists():
        return True
    try:
        marker.touch()
    except OSError:
        # Without a marker the hook cannot promise it will stop blocking, so it
        # does not start: reporting beats an unbreakable loop.
        return True
    return False


def main(argv: list[str]) -> int:
    as_hook = "--hook" in argv[1:]
    session_id = ""
    if as_hook:
        try:
            event = json.loads(sys.stdin.read() or "{}")
            session_id = str(event.get("session_id", "")) if isinstance(event, dict) else ""
        except (json.JSONDecodeError, UnicodeDecodeError):
            session_id = ""

    findings = run_preflight()
    actionable = [finding for finding in findings if finding.actionable]
    report = format_report(findings)

    if not as_hook:
        print(report)
        return 1 if actionable else 0

    if actionable and not _already_reported(session_id, actionable):
        print(report, file=sys.stderr)
        return 2
    if findings:
        json.dump(
            {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": report}},
            sys.stdout,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the hook and CLI
    raise SystemExit(main(sys.argv))
