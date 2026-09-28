"""Validate the PR review contract using only event JSON, local Git and the stdlib.

This checks the review package, not the truth of assertions or code correctness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

DRAFT_SECTIONS = (
    "Context",
    "Scope",
    "Non-goals",
    "Architecture",
    "Contract Impact",
    "Migration Impact",
    "Validation results",
)
READY_SECTIONS = (
    "Context",
    "Repo reality / Root cause",
    "Scope",
    "Non-goals",
    "Change cohesion",
    "Architecture",
    "Dependency Impact",
    "Contract Impact",
    "Migration Impact",
    "Financial Integrity",
    "Security / Privacy",
    "Deletion / Retention",
    "Validation results",
    "Deployment",
    "Review focus",
)
DECLARATIONS = {
    "Contract Impact": (
        "API Contract Changed",
        "Database Schema Changed",
        "Frontend Types Changed",
        "Financial Calculation Changed",
    ),
    "Migration Impact": (
        "Migration Required",
        "Backfill Required",
        "Destructive Change",
        "Rollback Safe",
    ),
}
EVIDENCE = (
    "Backend tests",
    "Frontend checks",
    "Migration test",
    "Manual validation",
    "Screenshots",
)
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|fill this|coming later)\b|Yes\s*/\s*No|\?{3}", re.I)
NA = re.compile(r"\b(?:N\s*/\s*A|not applicable)\b", re.I)
FINANCIAL = re.compile(
    r"\b(?:pricing|sales|payment[ _-]plans|collections|commissions|cashflow|"
    r"construction|unit[ _-]economics|currency[ _-]correction|refunds?|costs?|amounts?)\b",
    re.I,
)
GENERIC = {
    "fix",
    "update",
    "changes",
    "final",
    "stuff",
    "working",
    "misc",
    "bugfix",
    "pr",
    "fix stuff",
    "working on it",
    "see commits",
    "changed code",
    "fixed it",
    "they are related",
    "tests passed",
    "everything green",
    "fully tested",
}


@dataclass(frozen=True)
class Diff:
    paths: tuple[str, ...] = ()
    additions: int = 0


def without_comments(text: str) -> str:
    return re.sub(r"<!--.*?(?:-->|\Z)", "", text, flags=re.S)


def content(text: str) -> str:
    """Ignore checklist boilerplate and fence markers, retaining fenced field values."""
    return "\n".join(
        line
        for line in without_comments(text).splitlines()
        if not re.match(r"^\s*(?:`{3,}|~{3,}|[-*+]\s+\[[ xX]\])", line)
    ).strip()


def words(text: str) -> list[str]:
    return re.findall(r"\b[\w]+\b", text)


def meaningful(text: str) -> bool:
    text = content(text)
    # Empty labels from the template are not an explanation.
    text = "\n".join(line for line in text.splitlines() if not line.rstrip().endswith(":"))
    normalized = " ".join(words(text)).lower()
    return len(words(text)) >= 3 and normalized not in GENERIC


def parse_sections(body: str) -> dict[str, str]:
    """Read level-two headings outside fences. Reject duplicates instead of hiding them."""
    sections: dict[str, list[str]] = {}
    current = None
    fence = ""
    for line in without_comments(body).splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker[1]
            if not fence:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = ""
        heading = None if fence or marker else re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if heading:
            current = heading[1].strip().casefold()
            if current in sections:
                raise ValueError(
                    f"Duplicate section: ## {heading[1]}; keep one authoritative answer."
                )
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: content("\n".join(lines)) for name, lines in sections.items()}


def section(sections: dict[str, str], name: str) -> str:
    return sections.get(name.casefold(), "")


def fields(text: str, labels: tuple[str, ...]) -> dict[str, str]:
    """Accept inline or multiline answers, including the template's fenced blocks."""
    result: dict[str, str] = {}
    current = None
    lookup = {label.casefold(): label for label in labels}
    for line in content(text).splitlines():
        cleaned = re.sub(r"^\s*[-*+]\s+", "", line).replace("**", "").strip()
        match = re.match(r"^([^:]+):\s*(.*)$", cleaned)
        if match and match[1].casefold() in lookup:
            current = lookup[match[1].casefold()]
            if current in result:
                raise ValueError(f"Duplicate declaration/evidence label: {current}")
            result[current] = match[2]
        elif current and cleaned:
            result[current] += "\n" + cleaned
    return {key: value.strip() for key, value in result.items()}


def validate_title(title: str) -> list[str]:
    value = re.sub(r"^(?:\w+(?:\([^)]*\))?!?:|PR\s*\d+\s*[-—:])\s*", "", title, flags=re.I)
    if len(words(value)) < 2 or " ".join(words(value)).lower() in GENERIC:
        return ["Use a descriptive PR title identifying the change, not 'fix', 'update' or 'misc'."]
    return []


def validate_required_sections(sections: dict[str, str], required: tuple[str, ...]) -> list[str]:
    errors = []
    for name in required:
        if name.casefold() not in sections:
            errors.append(f"Missing required section: ## {name}")
        elif not meaningful(section(sections, name)):
            errors.append(
                f"## {name} needs useful content; comments, checkboxes and empty labels "
                "do not count."
            )
    return errors


def validate_placeholders(body: str) -> list[str]:
    text = without_comments(body)
    errors = [
        f"Ready PR contains unresolved placeholder: {match[0]}"
        for match in PLACEHOLDER.finditer(text)
    ]
    lines = content(text).splitlines()
    for index, line in enumerate(lines):
        match = NA.search(line)
        if match:
            # A reason may continue on the next line, but not in the next field/section.
            reason = line[match.end() :].strip(" .:;-—")
            for following in lines[index + 1 :]:
                if not following.strip() or following.lstrip().startswith("#") or ":" in following:
                    break
                reason += " " + following
            if len(words(reason)) < 3:
                errors.append(f"Explain non-applicability with a reason: {line.strip()}")
    return errors


def validate_contract_declarations(sections: dict[str, str]) -> list[str]:
    errors = []
    for name, labels in DECLARATIONS.items():
        answers = fields(section(sections, name), labels)
        for label in labels:
            if not re.fullmatch(
                r"(?:Yes|No)(?:\s*[—\u2013-]\s*\S.*)?\.?", answers.get(label, ""), re.I
            ):
                errors.append(f"## {name}: resolve '{label}: Yes / No' to one explicit Yes or No.")
    return errors


def limitation(value: str) -> bool:
    return (
        bool(
            re.search(
                r"\b(?:not run|could not run|unavailable|not available|not captured)\b", value, re.I
            )
        )
        and bool(re.search(r"(?:because|due to|unavailable|—| - |:)\s*\S", value, re.I))
        and len(words(value)) >= 6
    )


def evidence(value: str, kind: str) -> bool:
    if limitation(value):
        return True
    if NA.search(value):
        return False
    check = {
        "backend": (
            r"\b(?:pytest|unittest)\b|"
            r"\b(?:integration|functional|backend|regression) tests?\b"
        ),
        "frontend": (
            r"\b(?:tests?|typescript|tsc|lint|eslint|vitest|playwright)\b|"
            r"(?:production|npm run) build"
        ),
        "migration": r"\b(?:alembic|migration|roundtrip|upgrade|downgrade)\b",
    }[kind]
    result = r"\b(?:passed|failed|success(?:ful(?:ly)?)?|exit\s+0|\d+\s+passed)\b"
    return (
        bool(re.search(check, value, re.I) and re.search(result, value, re.I))
        and len(words(value)) >= 4
    )


def validate_validation_evidence(sections: dict[str, str]) -> list[str]:
    answers = fields(section(sections, "Validation results"), EVIDENCE)
    errors = []
    for label in EVIDENCE:
        value = answers.get(label, "")
        if not meaningful(value):
            errors.append(
                f"Validation results: populate '{label}:' with the exact check and result, "
                "limitation, or reasoned non-applicability."
            )
        elif re.search(r"\b(?:pending|not run yet)\b", value, re.I) and not limitation(value):
            errors.append(
                f"{label}: explain why validation has not run; "
                "a bare pending statement is only valid in Draft."
            )
    for label, kind in (
        ("Backend tests", "backend"),
        ("Frontend checks", "frontend"),
        ("Migration test", "migration"),
    ):
        value = answers.get(label, "")
        if value and not NA.search(value) and not evidence(value, kind):
            errors.append(
                f"{label}: identify the test/check and actual result, "
                "or explicitly explain why it could not run."
            )
    return errors


def validate_diff_sensitive_requirements(sections: dict[str, str], diff: Diff) -> list[str]:
    errors = []
    answers = fields(section(sections, "Validation results"), EVIDENCE)
    migrations = [p for p in diff.paths if p.startswith("app/db/migrations/versions/")]
    if migrations:
        for name, label in (
            ("Migration Impact", "Migration Required"),
            ("Contract Impact", "Database Schema Changed"),
        ):
            value = fields(section(sections, name), DECLARATIONS[name]).get(label, "")
            if not re.match(r"Yes\b", value, re.I):
                errors.append(f"{migrations[0]} is in the diff: declare '{label}: Yes'.")
        if not evidence(answers.get("Migration test", ""), "migration"):
            errors.append(
                "Migration files changed: 'Migration test' needs migration "
                "evidence or an explicit execution limitation, not N/A."
            )
    for prefix, suffix, label, kind in (
        ("frontend/src/", "", "Frontend checks", "frontend"),
        ("app/", ".py", "Backend tests", "backend"),
    ):
        if any(p.startswith(prefix) and p.endswith(suffix) for p in diff.paths) and not evidence(
            answers.get(label, ""), kind
        ):
            errors.append(
                f"{prefix} changed: '{label}' needs relevant test/check evidence "
                "or an explicit reason checks could not run. "
                "Ruff alone is not a backend functional test."
            )
    dependency_names = {
        "requirements.txt",
        "requirements-dev.txt",
        "package.json",
        "package-lock.json",
    }
    if any(Path(p).name in dependency_names for p in diff.paths):
        impact = section(sections, "Dependency Impact")
        delta = "\n".join(
            line for line in impact.splitlines() if not re.search(r":\s*None\.?\s*$", line, re.I)
        )
        if (
            not meaningful(delta)
            or NA.search(delta)
            or re.fullmatch(r"(?:none|no (?:dependency )changes)\.?", delta.strip(), re.I)
        ):
            errors.append(
                "Dependency manifest/lockfile changed: Dependency Impact must "
                "describe the actual delta (including version or lockfile-only "
                "changes)."
            )
    signal = " ".join(diff.paths).replace("_", " ") + " " + section(sections, "Scope")
    financial = section(sections, "Financial Integrity")
    if FINANCIAL.search(signal) and not NA.search(financial):
        labels = (
            "Source-of-truth fields",
            "Derived fields",
            "Formula changed",
            "Currency behavior",
            "Rounding behavior",
            "Reconciliation test",
        )
        values = fields(financial, labels)
        for label in labels:
            if not values.get(label):
                errors.append(
                    f"Financial change signal: Financial Integrity must describe '{label}:' "
                    "or explain why financial impact is not applicable."
                )
    return errors


def broad_scope(diff: Diff) -> bool:
    domains = {
        p.split("/")[2]
        for p in diff.paths
        if p.startswith("app/modules/") and len(p.split("/")) > 3
    }
    # Multiple domains are a review signal, not a claim that their work is unrelated.
    return len(diff.paths) >= 20 or diff.additions >= 800 or len(domains) >= 2


def validate_scope_cohesion(sections: dict[str, str], diff: Diff) -> list[str]:
    value = section(sections, "Change cohesion")
    if broad_scope(diff) and (not meaningful(value) or len(words(value)) < 12 or NA.search(value)):
        return [
            (
                "Broad/mixed PR (20+ files, 800+ additions, or multiple backend "
                "domains): explain in Change cohesion why these changes belong "
                "together or cannot safely be separated; otherwise split the PR."
            )
        ]
    return []


def validate(title: str, body: str, draft: bool, diff: Diff) -> list[str]:
    try:
        sections = parse_sections(body)
        required = DRAFT_SECTIONS if draft else READY_SECTIONS
        if not draft and any(p.startswith("frontend/src/") for p in diff.paths):
            required += ("Page layout",)
        errors = validate_required_sections(sections, required)
        errors += validate_scope_cohesion(sections, diff)
        if not draft:
            errors += validate_title(title)
            errors += validate_placeholders(body)
            errors += validate_contract_declarations(sections)
            errors += validate_validation_evidence(sections)
            errors += validate_diff_sensitive_requirements(sections, diff)
        return errors
    except ValueError as error:
        return [str(error)]


def inspect_diff(base: str, head: str, root: Path) -> Diff:
    """No shell or remote calls; fail closed on missing history. Renames include both paths."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
            timeout=30,
        ).stdout

    # Resolve refs before passing them to diff; --end-of-options prevents option injection.
    base_sha = git("rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}").strip()
    head_sha = git("rev-parse", "--verify", "--end-of-options", f"{head}^{{commit}}").strip()
    ancestor = git("merge-base", base_sha, head_sha).strip()
    stats = git(
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--numstat",
        "-z",
        ancestor,
        head_sha,
        "--",
    )
    paths = []
    additions = 0
    for entry in stats.split("\0"):
        if entry:
            added, _deleted, path = entry.split("\t", 2)
            paths.append(path)
            additions += int(added) if added != "-" else 0
    return Diff(tuple(paths), additions)


def event_pr(event: object) -> dict:
    if not isinstance(event, dict) or not isinstance(event.get("pull_request"), dict):
        raise ValueError("Event must contain a pull_request object.")
    pr = event["pull_request"]
    if not isinstance(pr.get("draft"), bool) or not isinstance(pr.get("title"), str):
        raise ValueError("Event must contain a string title and boolean draft state.")
    if pr.get("body") is not None and not isinstance(pr["body"], str):
        raise ValueError("PR body must be text or null.")
    for ref in ("base", "head"):
        if not isinstance(pr.get(ref), dict) or not re.fullmatch(
            r"[0-9a-fA-F]{40}", str(pr[ref].get("sha", ""))
        ):
            raise ValueError(f"Event must contain a valid pull_request.{ref}.sha.")
    return pr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--body-file", type=Path, help="local PR body; validates Ready unless --draft"
    )
    parser.add_argument("--title", default="")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)
    try:
        if args.body_file:
            title, body, draft = (
                args.title,
                args.body_file.read_text(encoding="utf-8-sig"),
                args.draft,
            )
            base, head = args.base, args.head
        else:
            event_path = os.environ.get("GITHUB_EVENT_PATH")
            if not event_path:
                raise ValueError("Set GITHUB_EVENT_PATH or use --body-file with --title.")
            pr = event_pr(json.loads(Path(event_path).read_text(encoding="utf-8-sig")))
            title, body, draft = pr["title"], pr.get("body") or "", pr["draft"]
            base, head = pr["base"]["sha"], pr["head"]["sha"]
        diff = inspect_diff(base, head, Path(__file__).resolve().parents[1])
        errors = validate(title, body, draft, diff)
        print(
            f"PR Quality: {'Draft' if draft else 'Ready'}; "
            f"{len(diff.paths)} changed paths; {diff.additions} additions."
        )
        if broad_scope(diff):
            print(
                "Broad/mixed scope signal: Change cohesion explanation required; "
                "size alone is not a rejection."
            )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        errors = [
            f"Cannot validate PR metadata/diff: {error}. Ensure the event is valid "
            "and base/head history is available (fetch-depth: 0)."
        ]
    if errors:
        print("PR QUALITY FAILED\n")
        for number, error in enumerate(errors, 1):
            print(f"{number}. {error}")
        print(
            "\nFix the PR description and edit the PR. The lightweight PR "
            "Quality workflow reruns automatically."
        )
        return 1
    print(
        "PR QUALITY PASSED. This validates the review package, not "
        "implementation correctness or merge readiness."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
