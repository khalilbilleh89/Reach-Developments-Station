"""Guards on the cutover's one operational surface.

Two properties this file exists for, and they are not the same property.

The first is what an operator relies on at two in the morning: **running this
tool does not change the system being migrated into unless they asked it to.**
That is carried by the shape of the action registry rather than by a flag, and
the tests below are what stop the shape drifting — a ``--dry-run`` that has to
be remembered is a ``--dry-run`` that gets forgotten.

The second is what the auditor relies on months later: **a run that was filed
stays filed.** Evidence is written under the batch it describes and an existing
artifact is refused rather than replaced, so no batch can quietly inherit
another's report and no rerun can quietly replace its own.

Note what is *not* claimed. Nothing here reads the body of an action, so no test
in this file can tell you an action performs no writes. What they prove is that
the registry and the reviewed set of target writers agree, which is a
consistency guarantee and is stated as one.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from scripts.migration import CONTRACT_VERSION
from scripts.migration.__main__ import (
    ACTIONS,
    EXIT_BLOCKED,
    EXIT_UNRECORDED,
    TARGET_MUTATION_ACTIONS,
    UNIDENTIFIED_BATCH,
    EvidenceRefused,
    build_parser,
    evidence_path,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

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


def batch(
    tmp_path: Path,
    *,
    content: str = "unit_reference\nU-1\n",
    batch_id: str | None = None,
    name: str = "work",
    contract_version: str | None = None,
) -> tuple[Path, Path]:
    """A sealed one-file bundle and the manifest describing it.

    ``batch_id`` and ``name`` are parameters so a test can put two genuinely
    different batches in one temporary directory, which is the only way to
    prove they do not collide. ``contract_version`` is one so a test can seal a
    batch under a contract that is not the one this code is currently on —
    which today requires widening ``SUPPORTED_CONTRACT_VERSIONS``, and which is
    the only way to tell the two apart.
    """
    from scripts.migration.manifest import load, seal

    bundle = tmp_path / name
    bundle.mkdir()
    (bundle / "units.csv").write_text(content, encoding="utf-8")

    declared = dict(DECLARATION)
    declared["batch_id"] = batch_id or DECLARATION["batch_id"]
    declared["contract_version"] = contract_version or CONTRACT_VERSION
    declaration = tmp_path / f"{name}-declaration.json"
    declaration.write_text(json.dumps(declared), encoding="utf-8")
    manifest = seal(load(declaration), directory=bundle, names=["units.csv"])

    path = tmp_path / f"{name}-manifest.json"
    path.write_text(json.dumps(manifest.as_dict()), encoding="utf-8")
    return bundle, path


# --------------------------------------------------------------------------- #
# Nothing changes the target unless it was asked for
# --------------------------------------------------------------------------- #


def test_the_registry_and_the_reviewed_set_of_target_writers_agree() -> None:
    """A consistency guarantee, and deliberately only that.

    This does not prove an action makes no writes — nothing here inspects the
    body of ``run``, and a test that claimed otherwise would be a false
    assurance in the one file whose job is not to give any. What it does prove
    is that an action cannot become a declared target writer without somebody
    editing ``TARGET_MUTATION_ACTIONS`` in the same change, which is the line
    review reads.
    """
    for action in ACTIONS:
        assert action.mutates_target is (action.name in TARGET_MUTATION_ACTIONS), action.name
    assert {"apply"} == TARGET_MUTATION_ACTIONS


def test_no_action_may_change_the_target_yet() -> None:
    """``apply`` is absent until it exists.

    A cutover command that accepts ``apply`` and quietly does nothing is
    discovered at the moment somebody believes a batch has landed.
    """
    assert [action.name for action in ACTIONS] == ["preflight"]
    assert not any(action.mutates_target for action in ACTIONS)


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


def test_nothing_is_written_unless_the_operator_named_somewhere_to_write_it(
    tmp_path: Path,
) -> None:
    """``--out`` is the whole of the filesystem opt-in."""
    bundle, manifest = batch(tmp_path)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)]) == 0
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


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


def test_preflight_never_changes_the_source_it_reads(tmp_path: Path) -> None:
    bundle, manifest = batch(tmp_path)
    (bundle / "units.csv").write_text("changed\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
    main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)])
    assert {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()} == before


def test_the_report_names_the_contract_the_batch_was_proved_under(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The manifest's declared contract, never whichever one this code is on.

    Today they are equal, and a test comparing the report against the current
    constant would pass no matter which of the two the code read — which is the
    trap. So this widens the supported set, seals a batch under the older
    contract, and asserts the report names *that* one. The day a second contract
    genuinely exists, "proved under contract 1" versus "read by code on
    contract 2" is the whole question an auditor is asking, and a report that
    always names the newest cannot answer it.
    """
    from scripts.migration import manifest as manifest_module

    older = "0"
    assert older != CONTRACT_VERSION
    monkeypatch.setattr(
        manifest_module,
        "SUPPORTED_CONTRACT_VERSIONS",
        frozenset({CONTRACT_VERSION, older}),
    )

    bundle, path = batch(tmp_path, contract_version=older)
    main(["preflight", "--bundle", str(bundle), "--manifest", str(path)])
    detail = next(
        line for line in capsys.readouterr().out.splitlines() if "manifest_readable" in line
    )
    assert f"contract {older}." in detail
    assert f"contract {CONTRACT_VERSION}." not in detail


# --------------------------------------------------------------------------- #
# Wrong command, wrong exit code
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("argv", "missing"),
    [
        (["preflight", "--manifest", "m.json"], "--bundle"),
        (["preflight", "--bundle", "work"], "--manifest"),
        (["preflight"], "--bundle"),
    ],
)
def test_a_missing_required_path_exits_two_not_one(
    argv: list[str], missing: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A typo is not a blocked batch, and the runbook branches on the difference.

    Exiting 1 for both would make a mistyped ``--manifest`` indistinguishable
    from a batch whose source had moved: one is fixed by retyping the command,
    the other by re-validating the whole extract. argparse already knows how to
    tell them apart, so the requirement lives there.
    """
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2
    assert raised.value.code != EXIT_BLOCKED
    assert missing in capsys.readouterr().err


def test_the_documented_exit_codes_hold_for_the_real_entry_point(tmp_path: Path) -> None:
    """Through ``python -m scripts.migration``, not through ``main`` in-process.

    The exit-code table in the module docstring is what a cutover runbook is
    written against, and a runbook runs the module. In-process tests never
    exercise ``sys.exit(main())``, so this one does.
    """
    bundle, manifest = batch(tmp_path)
    (bundle / "units.csv").write_text("moved\n", encoding="utf-8")

    def run(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.migration", *argv],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    assert run().returncode == 0
    assert run("preflight", "--manifest", str(manifest)).returncode == 2
    blocked = run("preflight", "--bundle", str(bundle), "--manifest", str(manifest))
    assert blocked.returncode == EXIT_BLOCKED
    assert "preflight: FAIL" in blocked.stdout


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


def test_a_blocking_result_exits_non_zero(tmp_path: Path) -> None:
    """The runbook branches on this, so it is asserted rather than assumed."""
    bundle, manifest = batch(tmp_path)
    (bundle / "units.csv").write_text("moved\n", encoding="utf-8")
    assert main(["preflight", "--bundle", str(bundle), "--manifest", str(manifest)]) == EXIT_BLOCKED


def test_every_action_takes_the_same_options_and_requires_the_same_two() -> None:
    """One surface, so the runbook reads the same for each step."""
    parser = build_parser()
    subcommands = {a.dest: a for a in parser._subparsers._group_actions}["action"]
    for action in ACTIONS:
        child = subcommands.choices[action.name]
        options = {a.dest: a for a in child._actions}
        assert {"bundle", "manifest", "out"} <= set(options)
        assert options["bundle"].required and options["manifest"].required
        assert not options["out"].required


# --------------------------------------------------------------------------- #
# Evidence: filed under its batch, and never replaced
# --------------------------------------------------------------------------- #


def test_evidence_is_filed_under_the_batch_it_describes(tmp_path: Path) -> None:
    bundle, manifest = batch(tmp_path)
    out = tmp_path / "evidence"
    code = main(
        ["preflight", "--bundle", str(bundle), "--manifest", str(manifest), "--out", str(out)]
    )
    assert code == 0

    artifact = out / DECLARATION["batch_id"] / "preflight.json"
    written = json.loads(artifact.read_text(encoding="utf-8"))
    assert written["result"] == "PASS"
    # The path and the contents have to agree, or the directory name is a label
    # somebody could trust while the file underneath describes something else.
    assert written["batch_id"] == artifact.parent.name


def test_two_batches_filed_together_do_not_overwrite_one_another(tmp_path: Path) -> None:
    """The defect the batch segment exists for.

    Both runs write ``preflight.json``. Without the batch in the path the
    second replaces the first, and what is left is one file describing one
    batch in a directory an operator believes covers both.
    """
    out = tmp_path / "evidence"
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    first_bundle, first_manifest = batch(tmp_path, batch_id=first_id, name="first")
    second_bundle, second_manifest = batch(
        tmp_path, batch_id=second_id, name="second", content="unit_reference\nU-9\n"
    )

    for b, m in ((first_bundle, first_manifest), (second_bundle, second_manifest)):
        assert main(["preflight", "--bundle", str(b), "--manifest", str(m), "--out", str(out)]) == 0

    written = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in out.rglob("preflight.json")
    }
    assert set(written) == {first_id, second_id}
    assert written[first_id]["batch_id"] == first_id
    assert written[second_id]["batch_id"] == second_id


def test_a_rerun_refuses_rather_than_replacing_its_own_earlier_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """And the exit code says the run was not recorded, not that it was blocked.

    The second run here genuinely fails its checks — the source moved between
    them — so this also fixes the precedence: an unfiled run exits
    ``EXIT_UNRECORDED`` whatever the checks said, because the operator's next
    step is the same either way and it is not "act on the result".
    """
    bundle, manifest = batch(tmp_path)
    out = tmp_path / "evidence"
    artifact = out / DECLARATION["batch_id"] / "preflight.json"
    argv = ["preflight", "--bundle", str(bundle), "--manifest", str(manifest), "--out", str(out)]

    assert main(argv) == 0
    first = artifact.read_text(encoding="utf-8")

    (bundle / "units.csv").write_text("moved\n", encoding="utf-8")
    assert main(argv) == EXIT_UNRECORDED

    captured = capsys.readouterr()
    assert str(artifact) in captured.err
    assert "preflight: FAIL" in captured.out, "the operator still sees what the run found"
    assert artifact.read_text(encoding="utf-8") == first, "the filed artifact is the filed one"


def test_a_run_that_could_not_name_its_batch_is_still_filed_somewhere_findable(
    tmp_path: Path,
) -> None:
    """A manifest too broken to name a batch is exactly when evidence matters."""
    bad = tmp_path / "manifest.json"
    bad.write_text("{not json", encoding="utf-8")
    out = tmp_path / "evidence"
    argv = ["preflight", "--bundle", str(tmp_path), "--manifest", str(bad), "--out", str(out)]

    assert main(argv) == EXIT_BLOCKED
    written = json.loads((out / UNIDENTIFIED_BATCH / "preflight.json").read_text(encoding="utf-8"))
    assert written["batch_id"] is None
    assert written["result"] == "FAIL"

    # A fixed name rather than a timestamp, so the second unidentified run
    # refuses instead of quietly filing a second opinion beside the first.
    assert main(argv) == EXIT_UNRECORDED


def test_a_batch_id_that_is_not_one_may_not_name_a_directory(tmp_path: Path) -> None:
    """The id becomes a path segment, so it is proved rather than trusted."""
    for hostile in ("../../etc", "..", "a/b", "", "batch one"):
        with pytest.raises(EvidenceRefused):
            evidence_path(tmp_path, action="preflight", batch_id=hostile)

    ok = str(uuid.uuid4())
    assert evidence_path(tmp_path, action="preflight", batch_id=ok) == (
        tmp_path / ok / "preflight.json"
    )
