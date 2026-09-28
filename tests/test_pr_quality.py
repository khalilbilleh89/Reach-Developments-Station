"""Review-package validation needs neither a database nor network access."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_backend_smoke as smoke  # noqa: E402
import ci_backend_tests as selector  # noqa: E402
import validate_pr_description as quality  # noqa: E402

TITLE = "feat(governance): enforce pull request quality across agents and devices"


# Only this pure tooling module opts out of application database setup.
# Domain tests retain the global migration/cleanup fixtures unchanged.
@pytest.fixture(scope="session")
def migrated_schema() -> None:
    """No schema is used by the PR validator tests."""


@pytest.fixture
def clean_database() -> None:
    """No rows are read or written by this module."""


def ready(**overrides: str) -> str:
    sections = {
        "Context": "PR descriptions previously omitted the evidence needed for independent review.",
        "Repo reality / Root cause": (
            "Reuse existing guards and CI; the missing contract was PR body validation."
        ),
        "Scope": "Add repository delivery-contract tooling and regression tests.",
        "Non-goals": "No product behavior or infrastructure deployment changes.",
        "Change cohesion": (
            "The validator, template, workflow and regression tests jointly "
            "enforce one repository review contract."
        ),
        "Architecture": (
            "A standard-library Python validator reads event metadata and local Git history."
        ),
        "Dependency Impact": (
            "Production Dependencies Added: None\nDevelopment Dependencies "
            "Added: None\nDependencies Removed: None"
        ),
        "Contract Impact": (
            "API Contract Changed: No\nDatabase Schema Changed: No\nFrontend "
            "Types Changed: No\nFinancial Calculation Changed: No"
        ),
        "Migration Impact": (
            "Migration Required: No\nBackfill Required: No\nDestructive "
            "Change: No\nRollback Safe: Yes"
        ),
        "Financial Integrity": (
            "Not applicable — repository tooling only; no financial data touched."
        ),
        "Security / Privacy": (
            "Read-only contents permission; event text is never executed as shell code."
        ),
        "Deletion / Retention": (
            "Not applicable — this PR creates no user-created persistent record."
        ),
        "Validation results": (
            "Backend tests: pytest tests/test_pr_quality.py — 42 "
            "passed\nFrontend checks: Not applicable — no frontend sources "
            "changed.\nMigration test: Not applicable — no migration or model "
            "schema changed.\nManual validation: Inspected the fixture "
            "failure messages successfully.\nScreenshots: Not applicable — no "
            "UI changes in tooling."
        ),
        "Deployment": (
            "Owner enables required GitHub checks after merge; reverting "
            "tooling restores the previous gate."
        ),
        "Review focus": (
            "Inspect failure behavior, diff handling and separation from application CI."
        ),
    }
    sections.update(overrides)
    return "\n\n".join(f"## {name}\n\n{value}" for name, value in sections.items())


def errors(
    body: str | None = None,
    *paths: str,
    draft: bool = False,
    title: str = TITLE,
    additions: int = 0,
) -> list[str]:
    return quality.validate(
        title, ready() if body is None else body, draft, quality.Diff(paths, additions)
    )


def test_valid_ready() -> None:
    assert errors() == []


def test_valid_draft_with_only_core_sections_and_pending_validation() -> None:
    sections = quality.parse_sections(ready())
    sections["validation results"] = (
        "Backend tests: Pending implementation.\nManual validation: Not run yet — Draft."
    )
    body = "\n\n".join(f"## {name}\n{sections[name.casefold()]}" for name in quality.DRAFT_SECTIONS)
    assert errors(body, draft=True) == []


def test_skimpy_draft_fails() -> None:
    assert "Missing required section: ## Context" in errors("## Summary\nfixed it", draft=True)


@pytest.mark.parametrize("name", quality.READY_SECTIONS)
def test_each_ready_section_is_required(name: str) -> None:
    body = ready().replace(f"## {name}\n", "## Other section\n")
    assert f"Missing required section: ## {name}" in errors(body)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "<!-- detailed answer hidden -->",
        "- [x] Reviewed carefully",
        "Working on it",
        "See commits",
        "Domain:\nCross-domain dependencies:",
    ],
)
def test_empty_or_meaningless_content_fails_both_states(value: str) -> None:
    assert errors(ready(Context=value))
    assert errors(ready(Context=value), draft=True)


@pytest.mark.parametrize(
    "value", ["TODO", "TBD", "FIXME", "fill this", "coming later", "Yes / No", "???"]
)
def test_unresolved_placeholders_fail_ready(value: str) -> None:
    assert any("placeholder" in e for e in errors(ready(Context=f"Explain this change: {value}")))


def test_comments_do_not_trigger_placeholder_failures() -> None:
    assert errors(ready() + "\n<!-- TODO Yes / No -->") == []


@pytest.mark.parametrize("value", ["N/A", "Not applicable", "N/A — none"])
def test_bare_non_applicability_fails(value: str) -> None:
    assert errors(ready(**{"Financial Integrity": value}))


def test_reasoned_non_applicability_on_next_line_passes() -> None:
    assert (
        errors(ready(**{"Financial Integrity": "N/A\nThis changes only repository tooling."})) == []
    )


@pytest.mark.parametrize("label", sum(quality.DECLARATIONS.values(), ()))
@pytest.mark.parametrize("value", ["", "Yes / No", "Maybe"])
def test_declarations_must_resolve(label: str, value: str) -> None:
    body = (
        ready()
        .replace(f"{label}: No", f"{label}: {value}")
        .replace(f"{label}: Yes", f"{label}: {value}")
    )
    assert any(label in e for e in errors(body))


def test_duplicate_sections_and_fields_are_not_silently_overwritten() -> None:
    assert any(
        "Duplicate section" in e for e in errors(ready() + "\n## Context\nDifferent answer here.")
    )
    assert any(
        "Duplicate declaration" in e
        for e in errors(
            ready().replace(
                "API Contract Changed: No", "API Contract Changed: No\nAPI Contract Changed: Yes"
            )
        )
    )


def test_fenced_template_fields_work_but_fenced_headings_do_not_count() -> None:
    body = (
        ready()
        .replace("API Contract Changed: No", "```text\nAPI Contract Changed: No")
        .replace("Financial Calculation Changed: No", "Financial Calculation Changed: No\n```")
    )
    assert errors(body) == []
    assert "context" not in quality.parse_sections(
        "```markdown\n## Context\nFake context here.\n```"
    )


def test_migration_and_schema_contradictions() -> None:
    result = errors(None, "app/db/migrations/versions/0040_example.py")
    assert any("Migration Required: Yes" in e for e in result)
    assert any("Database Schema Changed: Yes" in e for e in result)
    assert any("Migration test" in e for e in result)


def test_migration_evidence_or_explicit_limitation_passes() -> None:
    body = (
        ready()
        .replace("Migration Required: No", "Migration Required: Yes")
        .replace("Database Schema Changed: No", "Database Schema Changed: Yes")
        .replace(
            "Migration test: Not applicable — no migration or model schema changed.",
            (
                "Migration test: Alembic upgrade/downgrade not run locally "
                "because PostgreSQL was unavailable. CI required."
            ),
        )
    )
    assert errors(body, "app/db/migrations/versions/0040_example.py") == []


def test_frontend_requires_layout_and_relevant_evidence() -> None:
    result = errors(None, "frontend/src/example.tsx")
    assert any("Page layout" in e for e in result)
    assert any("frontend/src/ changed" in e for e in result)


@pytest.mark.parametrize(
    "evidence",
    [
        "npm run lint and production build — passed.",
        "TypeScript and frontend tests could not run because Node was unavailable; CI required.",
    ],
)
def test_frontend_evidence_or_reasoned_limitation(evidence: str) -> None:
    body = ready(
        **{"Page layout": "Existing full-page layout retained; no new record flows."}
    ).replace("Not applicable — no frontend sources changed.", evidence)
    assert errors(body, "frontend/src/example.tsx") == []


def test_backend_ruff_only_fails() -> None:
    body = ready().replace("pytest tests/test_pr_quality.py — 42 passed", "Ruff check . — passed")
    assert any(
        "backend functional test" in e for e in errors(body, "app/modules/projects/service.py")
    )


def test_backend_explicit_limitation_is_not_a_false_pass() -> None:
    body = ready().replace(
        "pytest tests/test_pr_quality.py — 42 passed",
        (
            "PostgreSQL integration tests not run locally because PostgreSQL "
            "was unavailable. Exact-head CI required."
        ),
    )
    assert errors(body, "app/modules/projects/service.py") == []


@pytest.mark.parametrize(
    "value",
    [
        "Tests passed.",
        "Backend: pass",
        "Pending implementation.",
        "Not run",
        "pytest",
        "Ruff passed successfully",
    ],
)
def test_backend_vague_or_unfinished_evidence_fails(value: str) -> None:
    body = ready().replace("pytest tests/test_pr_quality.py — 42 passed", value)
    assert errors(body)


def test_multiline_evidence_is_accepted() -> None:
    body = ready().replace(
        "Backend tests: pytest tests/test_pr_quality.py — 42 passed",
        (
            "Backend tests:\nNot run locally — PostgreSQL unavailable.\nCI "
            "PostgreSQL execution is still required."
        ),
    )
    assert errors(body, "app/example.py") == []


@pytest.mark.parametrize(
    "path",
    [
        "requirements.txt",
        "requirements-dev.txt",
        "package.json",
        "package-lock.json",
        "frontend/package.json",
        "frontend/package-lock.json",
    ],
)
def test_dependency_change_needs_delta(path: str) -> None:
    assert any("actual delta" in e for e in errors(None, path))
    assert (
        errors(
            ready(
                **{
                    "Dependency Impact": (
                        "Update React from version 18 to 19; regenerate its lockfile."
                    )
                }
            ),
            path,
        )
        == []
    )


@pytest.mark.parametrize(
    "title",
    [
        "fix",
        "Update",
        "changes",
        "final",
        "stuff",
        "working",
        "misc",
        "bugfix",
        "PR",
        "fix(ui): update",
    ],
)
def test_generic_ready_titles_fail(title: str) -> None:
    assert any("title" in e for e in errors(title=title))


@pytest.mark.parametrize("title", [TITLE, "PR 4 — Complete unit return-to-market workflow"])
def test_supported_title_styles(title: str) -> None:
    assert errors(title=title) == []


@pytest.mark.parametrize("draft", [True, False])
@pytest.mark.parametrize(
    "diff",
    [
        quality.Diff(tuple(f"docs/{i}.md" for i in range(20))),
        quality.Diff(("docs/readme.md",), 800),
        quality.Diff(("app/modules/projects/a.py", "app/modules/settings/b.py")),
    ],
)
def test_broad_scope_requires_real_cohesion(draft: bool, diff: quality.Diff) -> None:
    bad = quality.validate(TITLE, ready(**{"Change cohesion": "They are related."}), draft, diff)
    assert any("Broad/mixed PR" in e for e in bad)
    assert quality.validate(TITLE, ready(), draft, diff) == []


def test_financial_signal_requires_details_or_reasoned_exemption() -> None:
    body = ready(**{"Financial Integrity": "The calculations are still correct."})
    assert any("Source-of-truth fields" in e for e in errors(body, "app/modules/sales/service.py"))
    assert any(
        "Currency behavior" in e
        for e in errors(
            body.replace("repository delivery-contract tooling", "currency correction tooling")
        )
    )
    assert errors(ready(), "app/modules/sales/service.py") == []


def test_financial_field_explanations_pass() -> None:
    financial = "\n".join(
        f"{label}: Existing owner fields and behavior retained; regression evidence supplied."
        for label in (
            "Source-of-truth fields",
            "Derived fields",
            "Formula changed",
            "Currency behavior",
            "Rounding behavior",
            "Reconciliation test",
        )
    )
    assert errors(ready(**{"Financial Integrity": financial}), "app/modules/sales/service.py") == []


@pytest.mark.parametrize(
    "event", [None, {}, {"pull_request": {}}, {"pull_request": {"draft": "false", "title": TITLE}}]
)
def test_malformed_events_fail_closed(event: object) -> None:
    with pytest.raises(ValueError):
        quality.event_pr(event)


def test_cli_event_and_failure_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    event_file = tmp_path / "event.json"
    pr = {
        "title": TITLE,
        "body": ready(),
        "draft": False,
        "base": {"sha": "a" * 40},
        "head": {"sha": "b" * 40},
    }
    event_file.write_text(json.dumps({"pull_request": pr}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    seen = []

    def diff(base: str, head: str, root: Path) -> quality.Diff:
        seen.append((base, head))
        return quality.Diff()

    monkeypatch.setattr(quality, "inspect_diff", diff)
    assert quality.main([]) == 0
    assert seen == [("a" * 40, "b" * 40)]
    pr["body"] = None
    event_file.write_text(json.dumps({"pull_request": pr}), encoding="utf-8")
    assert quality.main([]) == 1
    output = capsys.readouterr().out
    assert (
        "PR QUALITY FAILED" in output
        and "## Context" in output
        and "reruns automatically" in output
    )


def test_cli_missing_event_or_history_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    assert quality.main([]) == 1
    body_file = tmp_path / "body.md"
    body_file.write_text(ready(), encoding="utf-8")
    assert (
        quality.main(
            [
                "--body-file",
                str(body_file),
                "--title",
                TITLE,
                "--base",
                "nonexistent-pr-quality-ref",
            ]
        )
        == 1
    )
    assert "Cannot validate PR metadata/diff" in capsys.readouterr().out


def test_real_git_diff_uses_merge_base_and_detects_renames_and_binary(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (tmp_path / "original.py").write_text("original\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "baseline")
    git("checkout", "-b", "feature")
    git("mv", "original.py", "renamed file.py")
    (tmp_path / "binary.bin").write_bytes(b"\0binary\0")
    git("add", ".")
    git("commit", "-m", "feature")
    head = git("rev-parse", "HEAD")
    git("checkout", "main")
    (tmp_path / "base-only.txt").write_text("not in the PR", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base advances")
    diff = quality.inspect_diff("main", head, tmp_path)
    assert set(diff.paths) == {"original.py", "renamed file.py", "binary.bin"}
    assert diff.additions == 1
    with pytest.raises(subprocess.CalledProcessError):
        quality.inspect_diff("--help", head, tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "scripts/validate_pr_description.py",
        "tests/test_pr_quality.py",
        ".github/workflows/pr-quality.yml",
    ],
)
def test_governance_is_targeted_in_fast_and_keeps_smoke_refusal(path: str) -> None:
    result = selector.select([path], selector.available_test_files(ROOT))
    assert not result.full
    assert "tests/test_pr_quality.py" in result.paths
    with pytest.raises(smoke.SmokeRefused):
        smoke.select([path])
