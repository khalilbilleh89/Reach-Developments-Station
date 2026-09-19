"""The agent guardrails decide what they claim to decide.

These tests exercise the repository's own rules, not Claude: given a command
string or a path and a branch, does the guard allow or deny it? A guard nobody
proved is a guard that blocks ordinary work or lets the dangerous case through,
and both are discovered in the same way — by asking it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

# Imported as modules, the way the CI selector tests import theirs: pytest
# collects any callable whose name begins with "test", and importing the
# guards by name would hand it a few.
import agent_guard  # noqa: E402
import agent_preflight  # noqa: E402
import ci_backend_tests as selector  # noqa: E402

SETTINGS_PATH = REPOSITORY_ROOT / ".claude" / "settings.json"


class TestTheShellGuardRefusesDestruction:
    """Commands that destroy work nobody can get back."""

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf build",
            "rm -fr /tmp/thing",
            "rm -r -f node_modules",
            "rm --recursive --force docs",
            "sudo rm -rf /var/lib/postgresql",
            "cd frontend && rm -rf out",
            "Remove-Item -Recurse -Force .\\build",
            "Remove-Item -Force -Recurse C:\\work\\out",
        ],
    )
    def test_recursive_forced_removal_is_denied(self, command: str) -> None:
        assert agent_guard.check_shell_command(command).denied

    @pytest.mark.parametrize(
        "command",
        [
            "git reset --hard",
            "git reset --hard origin/main",
            "git -C /home/user/repo reset --hard HEAD~1",
        ],
    )
    def test_hard_reset_is_denied(self, command: str) -> None:
        assert agent_guard.check_shell_command(command).denied

    @pytest.mark.parametrize("command", ["git clean -fd", "git clean -fdx", "git clean --force"])
    def test_cleaning_untracked_files_is_denied(self, command: str) -> None:
        assert agent_guard.check_shell_command(command).denied


class TestTheShellGuardProtectsSharedHistory:
    """Force pushes and anything landing on the protected branch."""

    @pytest.mark.parametrize(
        "command",
        ["git push --force", "git push -f origin feature/x", "git push origin +main"],
    )
    def test_a_force_push_is_denied(self, command: str) -> None:
        assert agent_guard.check_shell_command(command, "feature/x").denied

    def test_force_with_lease_is_allowed_because_it_is_the_safe_form(self) -> None:
        decision = agent_guard.check_shell_command(
            "git push --force-with-lease origin feature/x", "feature/x"
        )
        assert decision.allowed

    @pytest.mark.parametrize(
        "command",
        [
            "git push origin main",
            "git push upstream main",
            "git push origin HEAD:main",
            "git push origin feature/x:main",
            "git push origin feature/x:refs/heads/main",
        ],
    )
    def test_pushing_to_the_protected_branch_is_denied(self, command: str) -> None:
        assert agent_guard.check_shell_command(command, "feature/x").denied

    def test_a_bare_push_while_on_main_is_denied(self) -> None:
        assert agent_guard.check_shell_command("git push", "main").denied

    def test_a_bare_push_from_a_feature_branch_is_allowed(self) -> None:
        assert agent_guard.check_shell_command("git push", "feature/x").allowed

    def test_a_branch_merely_named_after_main_is_not_the_protected_branch(self) -> None:
        decision = agent_guard.check_shell_command("git push origin maintenance", "feature/x")
        assert decision.allowed


class TestAgentsDoNotMerge:
    """The repository's standing rule, enforced at the tool call."""

    @pytest.mark.parametrize(
        "command", ["gh pr merge 123", "gh pr merge 353 --squash --delete-branch", "gh pr merge"]
    )
    def test_the_merge_command_is_denied(self, command: str) -> None:
        assert agent_guard.check_shell_command(command).denied

    def test_the_merge_api_tool_is_denied_too(self) -> None:
        # `gh` is absent from several environments this repository is worked
        # in, so the CLI rule alone would be unenforced where it matters most.
        assert agent_guard.check_merge_tool("mcp__github__merge_pull_request").denied

    def test_an_ordinary_api_tool_is_untouched(self) -> None:
        assert agent_guard.check_merge_tool("mcp__github__create_pull_request").allowed


class TestTheShellGuardLeavesOrdinaryWorkAlone:
    """A guard that blocks real work gets switched off, and then guards nothing."""

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git diff --stat",
            "git log --oneline -5",
            "git fetch origin main",
            "git pull origin main",
            "git checkout -b feature/x",
            "git switch main",
            "git add -A",
            'git commit -m "feat: a thing"',
            "git push -u origin feature/x",
            "git push origin claude/gracious-allen-a1ebm7",
            "gh pr create --draft",
            "gh pr view 353",
            "pytest -q tests/test_agent_guardrails.py",
            "ruff check .",
            "ruff format --check .",
            "npm test",
            "npm run lint",
            "npm run build",
            "rm build/artifact.txt",
            "rm -f stale.log",
            "python scripts/ci_backend_tests.py --changed app/main.py",
        ],
    )
    def test_the_command_is_allowed(self, command: str) -> None:
        assert agent_guard.check_shell_command(command, "feature/x").allowed

    def test_a_dangerous_command_hidden_after_a_safe_one_is_still_found(self) -> None:
        decision = agent_guard.check_shell_command("git status && git push --force", "feature/x")
        assert decision.denied

    def test_an_unbalanced_quote_does_not_open_a_hole(self) -> None:
        assert agent_guard.check_shell_command('git reset --hard "', "feature/x").denied


class TestTheWriteGuardKeepsAgentsOffMain:
    def test_writing_on_main_is_denied(self, tmp_path: Path) -> None:
        decision = agent_guard.check_write(str(tmp_path / "app" / "x.py"), tmp_path, "main")
        assert decision.denied
        assert "feature branch" in decision.reason

    def test_writing_on_a_feature_branch_is_allowed(self, tmp_path: Path) -> None:
        assert agent_guard.check_write(
            str(tmp_path / "app" / "x.py"), tmp_path, "feature/x"
        ).allowed

    def test_an_unknown_branch_does_not_block_every_edit(self, tmp_path: Path) -> None:
        assert agent_guard.check_write(str(tmp_path / "app" / "x.py"), tmp_path, None).allowed

    def test_a_path_outside_the_repository_is_not_the_guard_s_business(
        self, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / "elsewhere" / "scratch.txt"
        assert agent_guard.check_write(str(outside), tmp_path / "repo", "main").allowed

    def test_windows_separators_resolve_to_the_same_decision(self, tmp_path: Path) -> None:
        windows_style = str(tmp_path / "app" / "x.py").replace("/", "\\")
        assert agent_guard.check_write(windows_style, tmp_path, "main").denied

    def test_a_relative_path_is_read_against_the_repository_root(self, tmp_path: Path) -> None:
        assert agent_guard.check_write("app/x.py", tmp_path, "main").denied


class TestTheWriteGuardProtectsSecrets:
    @pytest.mark.parametrize(
        "name",
        [".env", ".env.local", ".env.production", "frontend/.env", "frontend/.env.local"],
    )
    def test_a_secret_file_is_denied_even_on_a_feature_branch(
        self, tmp_path: Path, name: str
    ) -> None:
        decision = agent_guard.check_write(str(tmp_path / name), tmp_path, "feature/x")
        assert decision.denied
        assert ".env.example" in decision.reason

    @pytest.mark.parametrize("name", [".env.example", "frontend/.env.example", ".env.sample"])
    def test_an_example_file_is_allowed(self, tmp_path: Path, name: str) -> None:
        assert agent_guard.check_write(str(tmp_path / name), tmp_path, "feature/x").allowed

    def test_tracked_infrastructure_is_not_treated_as_a_secret(self, tmp_path: Path) -> None:
        assert agent_guard.check_write(str(tmp_path / "render.yaml"), tmp_path, "feature/x").allowed


class TestTheHookEntryPointIsSafe:
    """Hook input arrives from a tool call and is never trusted."""

    def test_unparseable_input_allows_rather_than_blocking_everything(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", _Stdin("not json at all"))
        assert agent_guard.main(["agent_guard.py", "shell"]) == 0

    def test_a_blocked_command_exits_two_with_a_reason(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        event = {"tool_name": "Bash", "tool_input": {"command": "git push --force"}}
        monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(event)))
        monkeypatch.setattr(agent_guard, "current_git_branch", lambda _root: "feature/x")
        assert agent_guard.main(["agent_guard.py", "shell"]) == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert payload["hookSpecificOutput"]["permissionDecisionReason"]

    def test_an_unknown_mode_is_reported_without_blocking_the_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", _Stdin("{}"))
        assert agent_guard.main(["agent_guard.py", "nonsense"]) == 1


class TestTheSettingsFileMatchesTheScripts:
    """A hook naming a script that does not exist is a guard that never runs."""

    def test_the_settings_file_parses(self) -> None:
        json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

    def test_the_expected_events_are_configured(self) -> None:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        assert set(settings["hooks"]) == {"PreToolUse", "Stop"}

    def test_every_referenced_script_exists(self) -> None:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        assert agent_preflight.validate_settings(settings) == []

    def test_a_missing_script_is_reported(self) -> None:
        broken = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3",
                                "args": ["${CLAUDE_PROJECT_DIR}/scripts/does_not_exist.py"],
                            }
                        ],
                    }
                ]
            }
        }
        findings = agent_preflight.validate_settings(broken)
        assert any("does_not_exist.py" in finding.detail for finding in findings)

    def test_every_hook_runs_a_repository_script_rather_than_an_inline_command(self) -> None:
        # The repository's rules live in scripts/ so every agent can reuse
        # them; a shell string in settings.json would make them Claude's alone.
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        for handlers in settings["hooks"].values():
            for handler in handlers:
                for entry in handler["hooks"]:
                    assert entry["command"] == "python3"
                    assert entry["args"][0].endswith((".py",))
                    assert "scripts/" in entry["args"][0]


class TestTheGuardrailsAreClassifiedForCi:
    """An unclassified file runs the entire backend suite. These are classified."""

    @pytest.mark.parametrize(
        "path",
        ["scripts/agent_guard.py", "scripts/agent_preflight.py", ".claude/settings.json"],
    )
    def test_changing_a_guardrail_file_does_not_run_the_whole_suite(self, path: str) -> None:
        available = sorted(
            str(candidate.relative_to(REPOSITORY_ROOT)).replace("\\", "/")
            for candidate in (REPOSITORY_ROOT / "tests").rglob("test_*.py")
        )
        result = selector.select([path], available)
        assert not result.full, f"{path} falls back to the full suite: {result.reasons}"
        assert "tests/test_agent_guardrails.py" in result.paths


class TestThePreflightFindsWhatItClaimsTo:
    def test_a_conflict_marker_is_found(self, tmp_path: Path) -> None:
        path = tmp_path / "thing.py"
        path.write_text("a = 1\n" + "<" * 7 + " HEAD\nb = 2\n", encoding="utf-8")
        findings = agent_preflight.check_conflict_markers([path])
        assert [finding.check for finding in findings] == ["conflict-markers"]

    def test_a_clean_file_yields_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "thing.py"
        path.write_text("a = 1\n", encoding="utf-8")
        assert agent_preflight.check_conflict_markers([path]) == []

    def test_malformed_json_is_found(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text('{"a": ', encoding="utf-8")
        findings = agent_preflight.check_json([path])
        assert [finding.check for finding in findings] == ["json"]

    def test_valid_json_yields_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "fine.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        assert agent_preflight.check_json([path]) == []

    def test_a_skill_without_frontmatter_is_found(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        path.write_text("# No frontmatter here\n", encoding="utf-8")
        findings = agent_preflight.check_skills([path])
        assert any("frontmatter" in finding.detail for finding in findings)

    def test_a_skill_missing_its_description_is_found(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: a-skill\n---\n\n# Body\n", encoding="utf-8")
        findings = agent_preflight.check_skills([path])
        assert any("description" in finding.detail for finding in findings)

    def test_every_shipped_skill_passes_the_check(self) -> None:
        skills = sorted((REPOSITORY_ROOT / ".claude" / "skills").glob("*/SKILL.md"))
        assert skills, "the skill library should not be empty"
        assert agent_preflight.check_skills(skills) == []

    def test_unavailable_tooling_is_not_reported_as_a_failure(self) -> None:
        unavailable = agent_preflight.Finding("eslint", "not installed", actionable=False)
        report = agent_preflight.format_report([unavailable])
        assert "could not run" in report
        assert "problem(s) to fix" not in report

    def test_a_clean_run_says_so(self) -> None:
        assert "clean" in agent_preflight.format_report([])


class _Stdin:
    """A stand-in for stdin carrying one hook payload."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> str:
        return self._text
