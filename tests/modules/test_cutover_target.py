"""The half of preflight that looks at the system being migrated into.

Four questions only the target can answer — is the schema the one this code was
written against, does the project exist, are the declared currencies configured,
did this batch already land — and one property that matters more than any of
them: **a report never lists a check it did not make.**

That last one is the reason ``INCOMPLETE`` exists. A preflight that ran half its
checks and said ``PASS`` would be acted on as though it had run all of them, and
the operator acting on it would be right to, because that is what the word
means. So the source half passing is not passing, and a database that cannot be
reached ends the report rather than filling it with passes nobody made.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.modules.access.models import User
from app.modules.audit.models import AuditEvent
from scripts.migration import CONTRACT_VERSION, target
from scripts.migration.__main__ import EXIT_BLOCKED, main
from scripts.migration.batch import claim
from scripts.migration.manifest import Manifest, load, seal

#: What ``tests/modules/conftest.py`` sets up, and what a manifest must name to
#: resolve against it.
PROJECT_CODE = "GALINI-BLU"
CURRENCY = "JOD"


def declaration(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "batch_id": str(uuid.uuid4()),
        "project_code": PROJECT_CODE,
        "source_system": "Legacy sales workbook",
        "extracted_at": datetime(2026, 9, 5, 6, 0, tzinfo=UTC).isoformat(),
        "cutover_date": date(2026, 9, 30).isoformat(),
        "expected_currencies": [CURRENCY],
        "operator": "A. Operator",
        "reason": "cutover trial",
        "contract_version": CONTRACT_VERSION,
    }
    payload.update(overrides)
    return payload


def sealed(tmp_path: Path, **overrides: object) -> tuple[Path, Path, Manifest]:
    """A sealed one-file bundle, its manifest on disk, and the parsed manifest."""
    bundle = tmp_path / "work"
    bundle.mkdir()
    (bundle / "units.csv").write_text("unit_reference\nU-1\n", encoding="utf-8")

    declared = tmp_path / "declaration.json"
    declared.write_text(json.dumps(declaration(**overrides)), encoding="utf-8")
    manifest = seal(load(declared), directory=bundle, names=["units.csv"])

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest.as_dict()), encoding="utf-8")
    return bundle, path, manifest


def rows(checks: list[dict[str, object]]) -> dict[str, str]:
    return {str(check["check"]): str(check["result"]) for check in checks}


# --------------------------------------------------------------------------- #
# Both halves, end to end
# --------------------------------------------------------------------------- #


def test_a_batch_that_passes_both_halves_is_the_only_thing_that_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], project_id: str
) -> None:
    """The one path to exit zero, through the entry point a runbook uses."""
    bundle, path, _ = sealed(tmp_path)
    code = main(
        ["--json", "preflight", "--bundle", str(bundle), "--manifest", str(path), "--target"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["result"] == "PASS", payload["checks"]
    assert payload["target_checked"] is True
    assert code == 0
    assert rows(payload["checks"]) == {
        "manifest_readable": "PASS",
        "bundle_present": "PASS",
        "source_unchanged": "PASS",
        "database_reachable": "PASS",
        "schema_at_expected_head": "PASS",
        "project_known": "PASS",
        "currencies_configured": "PASS",
        "batch_not_applied": "PASS",
    }


def test_a_source_side_failure_still_skips_the_target_half(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], project_id: str
) -> None:
    """An unreadable manifest names no batch, so there is nothing to ask about.

    The target checks are not "skipped for speed" — without a manifest there is
    no project code, no currency list and no batch id to look up, so asking is
    not possible rather than merely expensive.
    """
    bad = tmp_path / "manifest.json"
    bad.write_text("{not json", encoding="utf-8")
    code = main(
        ["--json", "preflight", "--bundle", str(tmp_path), "--manifest", str(bad), "--target"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == EXIT_BLOCKED
    assert payload["result"] == "FAIL"
    assert payload["target_checked"] is False
    assert set(rows(payload["checks"])) == {"manifest_readable"}


# --------------------------------------------------------------------------- #
# What each target check refuses
# --------------------------------------------------------------------------- #


def test_an_unknown_project_blocks_the_batch(tmp_path: Path, project_id: str) -> None:
    """A cutover resolves a project. It never creates one."""
    _, _, manifest = sealed(tmp_path, project_code="NO-SUCH-PROJECT")
    checks = target.inspect(manifest)
    assert rows(checks)["project_known"] == "FAIL"
    detail = next(c for c in checks if c["check"] == "project_known")["detail"]
    assert "NO-SUCH-PROJECT" in str(detail)


def test_a_currency_the_system_does_not_have_blocks_the_batch(
    tmp_path: Path, project_id: str
) -> None:
    """Refused, never created and never converted into.

    There is no FX in this system, so a declared currency the target does not
    hold is not a rate lookup away from being usable — it is a batch that would
    write amounts nobody can interpret.
    """
    _, _, manifest = sealed(tmp_path, expected_currencies=[CURRENCY, "XXX"])
    checks = target.inspect(manifest)
    assert rows(checks)["currencies_configured"] == "FAIL"
    assert "XXX" in str(next(c for c in checks if c["check"] == "currencies_configured")["detail"])


def test_a_batch_that_already_landed_blocks(
    tmp_path: Path, db: Session, admin: User, project_id: str
) -> None:
    """The question ``batch.py`` exists to answer, asked before anything is written."""
    _, _, manifest = sealed(tmp_path)
    assert rows(target.inspect(manifest))["batch_not_applied"] == "PASS"

    claim(db, manifest, actor_user_id=admin.id)
    db.commit()

    checks = target.inspect(manifest)
    assert rows(checks)["batch_not_applied"] == "FAIL"
    assert str(manifest.batch_id) in str(
        next(c for c in checks if c["check"] == "batch_not_applied")["detail"]
    )


def test_a_database_at_the_wrong_head_blocks_the_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_id: str
) -> None:
    """The failure this check exists for, made to actually happen.

    Written first as "both revisions appear in the detail", which survived a
    mutation that compared the database against itself: the two strings are
    identical in a migrated test database, so the assertion held whichever value
    the code read. The falsification found it. The property is that a mismatch
    *blocks*, so the test creates one.

    Applying against a schema this code was not written for writes to columns
    whose meaning it has guessed, which is why it blocks rather than warns.
    """
    _, _, manifest = sealed(tmp_path)
    monkeypatch.setattr(target, "applied_head", lambda: "0007_not_the_head")

    checks = target.inspect(manifest)
    assert rows(checks)["schema_at_expected_head"] == "FAIL"

    detail = str(next(c for c in checks if c["check"] == "schema_at_expected_head")["detail"])
    assert "0007_not_the_head" in detail, "the operator needs to know where the database is"
    assert target.expected_head() in detail, "and what this code expected"


def test_a_database_at_the_expected_head_passes(tmp_path: Path, project_id: str) -> None:
    """The other side of it, so the check is not simply always failing."""
    _, _, manifest = sealed(tmp_path)
    assert rows(target.inspect(manifest))["schema_at_expected_head"] == "PASS"
    assert target.applied_head() == target.expected_head()


# --------------------------------------------------------------------------- #
# The honesty properties
# --------------------------------------------------------------------------- #


def test_an_unreachable_database_reports_no_check_it_never_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_id: str
) -> None:
    """One failure, and no passes invented to keep it company.

    A report listing four passes it never made is worse than one listing a
    single failure, because the first is believed. The detail has to say so
    outright: "nothing below this line has been established" is what stops a
    reader treating a short report as a clean one.
    """
    monkeypatch.setattr(
        target,
        "applied_head",
        lambda: (_ for _ in ()).throw(OperationalError("SELECT 1", {}, Exception("no route"))),
    )
    _, _, manifest = sealed(tmp_path)
    checks = target.inspect(manifest)

    assert list(rows(checks)) == ["database_reachable"]
    assert rows(checks)["database_reachable"] == "FAIL"
    assert "not attempted" in str(checks[0]["detail"])


def test_the_target_checks_write_nothing(tmp_path: Path, db: Session, project_id: str) -> None:
    """Asking whether last night's batch landed may not change anything.

    ``inspect`` opens its own session and rolls it back. If it ever grew a write
    — a "we looked at this" marker, say — an operator's read-only question would
    start mutating the system they were asking about.
    """
    _, _, manifest = sealed(tmp_path)
    before = db.scalars(select(func.count()).select_from(AuditEvent)).one()
    target.inspect(manifest)
    db.rollback()
    assert db.scalars(select(func.count()).select_from(AuditEvent)).one() == before
