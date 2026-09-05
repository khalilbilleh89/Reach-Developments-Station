"""Guards on the batch manifest and the hash chain it carries.

The failure this file is about is mundane and would be discovered too late: an
operator validates a bundle, spends an afternoon fixing rejects in the source,
and applies without validating again. The apply then writes something no report
describes, and the reconciliation that follows compares the target against
totals from the wrong file.
"""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

import pytest

from scripts.migration import CONTRACT_VERSION
from scripts.migration.manifest import (
    Manifest,
    ManifestError,
    hash_file,
    load,
    seal,
    verify_unchanged,
)

DECLARATION = {
    "batch_id": "0f9a1f4e-1f2b-4c3d-9e8f-a1b2c3d4e5f6",
    "project_code": "DEMO-1",
    "source_system": "Legacy sales workbook",
    "extracted_at": "2026-09-05T06:00:00+00:00",
    "cutover_date": "2026-09-30",
    "expected_currencies": ["aed"],
    "operator": "A. Operator",
    "reason": "MVP 1.0 cutover trial",
}


def bundle(tmp_path: Path, **files: str) -> Path:
    directory = tmp_path / "bundle"
    directory.mkdir()
    for name, content in files.items():
        (directory / f"{name}.csv").write_text(content, encoding="utf-8")
    return directory


def declared(tmp_path: Path, **overrides: object) -> Manifest:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({**DECLARATION, **overrides}), encoding="utf-8")
    return load(path)


# --------------------------------------------------------------------------- #
# What an operator must state
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("field", sorted(DECLARATION))
def test_every_declared_field_is_required(tmp_path: Path, field: str) -> None:
    """None of these has a safe default, so none of them gets one."""
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({k: v for k, v in DECLARATION.items() if k != field}), "utf-8")
    with pytest.raises(ManifestError) as refusal:
        load(path)
    assert field in str(refusal.value)


def test_the_cutover_date_is_declared_and_never_todays_date(tmp_path: Path) -> None:
    """A batch prepared Friday and applied Monday must not move its own cutover.

    The opening cash position is true as at one specific business day. Deriving
    that day from the clock would make the same batch mean two different things
    depending on when somebody got round to running it.
    """
    manifest = declared(tmp_path)
    assert manifest.cutover_date == date(2026, 9, 30)
    assert manifest.cutover_date != date.today()


def test_currencies_are_normalised_but_never_converted(tmp_path: Path) -> None:
    """There is no FX in this system and a cutover will not be where one appears."""
    assert declared(tmp_path, expected_currencies=["aed", "usd"]).expected_currencies == (
        "AED",
        "USD",
    )


def test_a_malformed_manifest_says_what_is_wrong_with_it(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="not valid JSON"):
        load(path)
    with pytest.raises(ManifestError, match="No manifest at"):
        load(tmp_path / "absent.json")
    with pytest.raises(ManifestError, match="must be a UUID"):
        declared(tmp_path, batch_id="not-a-uuid")
    with pytest.raises(ManifestError, match="ISO 8601"):
        declared(tmp_path, cutover_date="30/09/2026")


def test_the_contract_version_travels_with_the_batch(tmp_path: Path) -> None:
    """ "Which intake contract was this validated against?" is an auditor's question."""
    assert declared(tmp_path).contract_version == CONTRACT_VERSION


def test_the_adapter_version_is_unknown_rather_than_invented(tmp_path: Path) -> None:
    """No adapter exists until the real source does, and the manifest says so."""
    assert declared(tmp_path).adapter_version is None


# --------------------------------------------------------------------------- #
# The hash chain
# --------------------------------------------------------------------------- #


def test_sealing_records_every_file_in_the_bundle(tmp_path: Path) -> None:
    directory = bundle(tmp_path, units="unit_reference\nU-1\n", sales="spa\nSPA-1\n")
    sealed = seal(declared(tmp_path), directory=directory, names=["units.csv", "sales.csv"])
    assert [source.name for source in sealed.files] == ["sales.csv", "units.csv"]
    assert sealed.files[1].sha256 == hash_file(directory / "units.csv")
    assert sealed.files[1].bytes == (directory / "units.csv").stat().st_size


def test_sealing_refuses_a_bundle_that_is_missing_a_file(tmp_path: Path) -> None:
    directory = bundle(tmp_path, units="unit_reference\nU-1\n")
    with pytest.raises(ManifestError, match=r"missing sales\.csv"):
        seal(declared(tmp_path), directory=directory, names=["units.csv", "sales.csv"])


def test_an_unchanged_bundle_verifies(tmp_path: Path) -> None:
    directory = bundle(tmp_path, units="unit_reference\nU-1\n")
    verify_unchanged(
        seal(declared(tmp_path), directory=directory, names=["units.csv"]), directory=directory
    )


def test_one_edited_byte_refuses_the_apply(tmp_path: Path) -> None:
    """The defect this module exists for: fix three rows, forget to re-validate."""
    directory = bundle(tmp_path, units="unit_reference\nU-1\n")
    sealed = seal(declared(tmp_path), directory=directory, names=["units.csv"])
    (directory / "units.csv").write_text("unit_reference\nU-2\n", encoding="utf-8")
    with pytest.raises(ManifestError) as refusal:
        verify_unchanged(sealed, directory=directory)
    message = str(refusal.value)
    assert "units.csv changed" in message
    assert "Run validate again" in message


def test_a_deleted_file_refuses_the_apply(tmp_path: Path) -> None:
    directory = bundle(tmp_path, units="unit_reference\nU-1\n")
    sealed = seal(declared(tmp_path), directory=directory, names=["units.csv"])
    (directory / "units.csv").unlink()
    with pytest.raises(ManifestError, match=r"units\.csv is gone"):
        verify_unchanged(sealed, directory=directory)


def test_an_unsealed_manifest_cannot_authorise_an_apply(tmp_path: Path) -> None:
    """No hashes means nothing proves the source held still. That is a refusal."""
    directory = bundle(tmp_path, units="unit_reference\nU-1\n")
    with pytest.raises(ManifestError, match="no file hashes"):
        verify_unchanged(declared(tmp_path), directory=directory)


#: Names an escape hatch would plausibly be given. Matched against real
#: parameters and assignments rather than against the text of the file: the
#: docstring on ``verify_unchanged`` promises there is no ``--force``, and a
#: substring search cannot tell that promise apart from the thing it forbids.
_ESCAPES = frozenset({"force", "skip_hash", "ignore_hash", "no_verify", "allow_changed", "unsafe"})


def test_there_is_no_way_to_override_the_hash_refusal() -> None:
    """The remedy is to validate again, and there is no second remedy.

    A ``--force`` here would not weaken the guarantee, it would delete it: the
    only thing making a validation report describe the file being applied is
    that nothing can apply a file the report does not describe.
    """
    tree = ast.parse(Path("scripts/migration/manifest.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            arguments = node.args
            names = {
                argument.arg
                for argument in [
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                ]
            }
            assert not (names & _ESCAPES), f"{node.name} takes {sorted(names & _ESCAPES)}"
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            assert node.id not in _ESCAPES, node.id
