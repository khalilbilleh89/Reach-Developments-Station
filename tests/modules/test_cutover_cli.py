"""Guards on the cutover's one operational surface.

The property this file exists for is the one an operator relies on at two in the
morning: **running this tool does not change anything unless they asked it to.**
That is enforced by shape rather than by a flag, and the tests below are what
stop the shape drifting — a ``--dry-run`` that has to be remembered is a
``--dry-run`` that gets forgotten.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from scripts.migration import CONTRACT_VERSION
from scripts.migration.__main__ import (
    ACTIONS,
    EXIT_BLOCKED,
    WRITE_ACTIONS,
    build_parser,
    main,
)

DECLARATION = {
    "batch_id": str(uuid.uuid4()),
    "project_code": "DEMO-1",
    "source_system": "Legacy sales workbook",
    "extracted_at": datetime(2026, 9, 5, 6, 0, tzinfo=UTC).isoformat(),
    "cutover_date": date(2026, 9, 30).isoformat(),
    "expected_currencies": ["AED"],
    "operator": "A. Operator",
    "reason": "cutover trial",
    "contract_version": CONTRACT_VERSION,
}


def batch(tmp_path: Path, *, content: str = "unit_reference\nU-1\n") -> tuple[Path, Path]:
    """A sealed one-file bundle and the manifest describing it."""
    from scripts.migration.manifest import load, seal

    bundle = tmp_path / "work"
    bundle.mkdir()
    (bundle / "units.csv").write_text(content, encoding="utf-8")

    declaration = tmp_path / "declaration.json"
    declaration.write_text(json.dumps(DECLARATION), encoding="utf-8")
    manifest = seal(load(declaration), directory=bundle, names=["units.csv"])

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest.as_dict()), encoding="utf-8")
    return bundle, path


# --------------------------------------------------------------------------- #
# Nothing writes unless it was asked for
# --------------------------------------------------------------------------- #


def test_only_apply_may_ever_write() -> None:
    """The safety property, asserted against the registry rather than the docs.

    ``writes`` on an action is not a comment. An action that grows a write path
    without moving into ``WRITE_ACTIONS`` fails here, which is the point: the
    write surface is reviewable before the code that uses it lands.
    """
    for action in ACTIONS:
        assert action.writes is (action.name in WRITE_ACTIONS), action.name
    assert {"apply"} == WRITE_ACTIONS


def test_no_action_is_registered_as_a_writer_yet() -> None:
    """``apply`` is absent until it exists.

    A cutover command that accepts ``apply`` and quietly does nothing is
    discovered at the moment somebody believes a batch has landed.
    """
    assert [action.name for action in ACTIONS] == ["preflight"]
    assert not any(action.writes for action in ACTIONS)


def test_running_the_module_with_no_action_does_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The default path is the harmless one."""
    before = sorted(p.name for p in tmp_path.iterdir())
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_there_is_no_flag_that_promotes_a_read_only_action() -> None:
    """No ``--write``, no ``--force``, no ``--yes``. The action is the opt-in."""
    text = Path("scripts/migration/__main__.py").read_text(encoding="utf-8")
    for smell in ("--write", "--force", "--yes", "--no-dry-run", "--execute", "--commit"):
        assert smell not in text, smell


# --------------------------------------------------------------------------- #
# preflight
# --------------------------------------------------------------------------- #


def test_preflight_passes_on_an_untouched_batch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, manifest = batch(tmp_path)
    code = main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)])
    assert code == 0
    assert "preflight: PASS" in capsys.readouterr().out


def test_preflight_blocks_when_the_source_moved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The defect the hash chain exists for, reached through the CLI."""
    bundle, manifest = batch(tmp_path)
    (bundle / "units.csv").write_text("unit_reference\nU-2\n", encoding="utf-8")
    code = main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)])
    assert code == EXIT_BLOCKED
    out = capsys.readouterr().out
    assert "preflight: FAIL" in out
    assert "source_unchanged" in out


def test_preflight_blocks_on_an_unreadable_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "manifest.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["preflight", "--bundle", str(tmp_path), "--manifest", str(bad)]) == EXIT_BLOCKED
    assert "manifest_readable" in capsys.readouterr().out


def test_preflight_writes_nothing_even_when_it_fails(tmp_path: Path) -> None:
    bundle, manifest = batch(tmp_path)
    (bundle / "units.csv").write_text("changed\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
    main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)])
    assert {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()} == before


# --------------------------------------------------------------------------- #
# Output the runbook can use
# --------------------------------------------------------------------------- #


def test_json_prints_one_object_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """So the runbook can pipe it without stripping a banner off the front."""
    bundle, manifest = batch(tmp_path)
    main(["--json", "preflight", "--bundle", str(bundle), "--manifest", str(manifest)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "preflight"
    assert payload["result"] == "PASS"
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["blocking"] == 0


def test_the_report_names_the_batch_it_describes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An artifact that cannot say which batch it is about is not evidence."""
    bundle, manifest = batch(tmp_path)
    main(["--json", "preflight", "--bundle", str(bundle), "--manifest", str(manifest)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["batch_id"] == DECLARATION["batch_id"]
    assert payload["project_code"] == "DEMO-1"
    assert payload["cutover_date"] == "2026-09-30"


def test_out_writes_the_report_where_the_operator_asked(tmp_path: Path) -> None:
    bundle, manifest = batch(tmp_path)
    out = tmp_path / "evidence"
    main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest), "--out", str(out)])
    written = json.loads((out / "preflight.json").read_text(encoding="utf-8"))
    assert written["result"] == "PASS"


def test_a_blocking_result_exits_non_zero(tmp_path: Path) -> None:
    """The runbook branches on this, so it is asserted rather than assumed."""
    bundle, manifest = batch(tmp_path)
    (bundle / "units.csv").write_text("moved\n", encoding="utf-8")
    assert main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)]) == EXIT_BLOCKED


def test_a_missing_required_path_is_refused_not_guessed(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["preflight", "--manifest", str(tmp_path / "m.json")])


def test_every_action_takes_the_same_four_options() -> None:
    """One surface, so the runbook reads the same for each step."""
    parser = build_parser()
    actions = {a.dest: a for a in parser._subparsers._group_actions}
    for name in [action.name for action in ACTIONS]:
        child = actions["action"].choices[name]
        assert {"bundle", "manifest", "out"} <= {a.dest for a in child._actions}
