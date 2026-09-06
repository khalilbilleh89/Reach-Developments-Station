"""The synthetic bundle: coherent, complete, and unmistakably not real.

Two jobs. The first is to be *correct* — the shape the importer will be tested
against, and the shape an operator preparing a real batch has to match. A
fixture whose foreign keys do not line up teaches the importer to accept
something no real bundle looks like.

The second is to be *obviously fictional*, and that one is asserted rather than
intended. This data is committed to a history that outlives the migration. Every
email address ends in a domain that cannot resolve, every telephone number is in
the block reserved for fiction, every identity document reads ``ID-SAMPLE-nnnn``.
The day somebody pastes a real row in "just to reproduce a bug", this file fails
before the commit does.

A run against this bundle is **not a trial migration**, and the distinction is
not pedantry: this exercises the machinery on data whose answers are known in
advance. A trial migration is the same machinery pointed at the client's real
extract, and it is blocked because the extract does not exist.
"""

from __future__ import annotations

import csv
import json
import re
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.migration import CONTRACT_VERSION
from scripts.migration.__main__ import main
from scripts.migration.manifest import load, seal
from scripts.migration.reporting import spreadsheet_safe
from tests.modules.test_cutover_intake_contract import REPO_ROOT, import_order

BUNDLE = REPO_ROOT / "tests/fixtures/cutover"

#: The project the bundle belongs to. Not created by the batch — the contract's
#: correction — so it is the fictional project this suite already sets up.
PROJECT_CODE = "GALINI-BLU"
CURRENCY = "JOD"

#: Reserved by RFC 2606 and unresolvable by design.
_EMAIL = re.compile(r"^[^@]+@example\.invalid$")
#: The 555-01xx block, reserved for fiction.
_PHONE = re.compile(r"^\+1-555-01\d{2}$")
_IDENTITY = re.compile(r"^ID-SAMPLE-\d{4}$")
_TAX = re.compile(r"^TAX-SAMPLE-\d{4}$")


def rows(name: str) -> list[dict[str, str]]:
    with (BUNDLE / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def values(name: str, column: str) -> set[str]:
    return {row[column] for row in rows(name)}


# --------------------------------------------------------------------------- #
# Complete against the contract
# --------------------------------------------------------------------------- #


def test_the_bundle_holds_exactly_the_files_the_contract_orders() -> None:
    """Both directions, because either gap is a different lie.

    A missing file means the importer is never exercised on it; an extra one
    means the fixture asserts a shape the contract does not describe, and the
    two would drift until somebody trusted the wrong one.
    """
    present = sorted(path.stem for path in BUNDLE.glob("*.csv"))
    assert present == sorted(import_order())


def test_every_file_parses_and_every_row_is_the_width_of_its_header() -> None:
    """A short row is a shifted row, and a shifted row is wrong data that parses."""
    for name in import_order():
        with (BUNDLE / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            assert header, f"{name}.csv has no header"
            assert len(header) == len(set(header)), f"{name}.csv repeats a column"
            for number, row in enumerate(reader, start=2):
                assert len(row) == len(header), f"{name}.csv row {number} is {len(row)} wide"


def test_every_row_belongs_to_the_one_project() -> None:
    """One batch, one project. A stray code would be a silent cross-project write."""
    for name in import_order():
        assert values(name, "project_code") == {PROJECT_CODE}, name


# --------------------------------------------------------------------------- #
# Coherent within itself
# --------------------------------------------------------------------------- #


def test_the_hierarchy_resolves_at_every_level() -> None:
    """Phase to building to floor to unit, each reference present.

    This is the fixture's real content. An importer tested against a bundle
    whose foreign keys do not resolve learns to accept something no correct
    bundle looks like.
    """
    phases = values("phases", "code")
    assert values("buildings", "phase_code") <= phases

    buildings = {(row["phase_code"], row["code"]) for row in rows("buildings")}
    assert {(row["phase_code"], row["building_code"]) for row in rows("floors")} <= buildings

    floors = {(row["building_code"], row["code"]) for row in rows("floors")}
    assert {(row["building_code"], row["floor_code"]) for row in rows("units")} <= floors


def test_area_schedules_and_their_values_line_up() -> None:
    """Every schedule names a unit, every value names a schedule and a type."""
    units = values("units", "unit_reference")
    schedules = {
        (row["unit_reference"], row["revision_code"]) for row in rows("unit_area_schedules")
    }
    assert {reference for reference, _ in schedules} <= units

    area_types = values("area_types", "code")
    for row in rows("unit_area_values"):
        assert (row["unit_reference"], row["revision_code"]) in schedules, row
        assert row["area_type_code"] in area_types, row
        assert Decimal(row["raw_area"]) >= 0, row


def test_at_most_one_approved_schedule_per_unit() -> None:
    """``uq_unit_area_schedules_current`` would refuse the second at the database.

    Caught here so the reject names a row in a file rather than surfacing as an
    integrity error nobody can locate.
    """
    approved: dict[str, int] = defaultdict(int)
    for row in rows("unit_area_schedules"):
        if row["status"] == "approved":
            approved[row["unit_reference"]] += 1
    assert not [unit for unit, count in approved.items() if count > 1]


def test_every_clients_shares_sum_to_exactly_one() -> None:
    """As ``Decimal``. A hundred percent that is 0.9999999999 is not a hundred."""
    shares: dict[str, Decimal] = defaultdict(Decimal)
    primaries: dict[str, int] = defaultdict(int)
    clients = values("clients", "client_number")

    for row in rows("client_parties"):
        assert row["client_number"] in clients, row
        shares[row["client_number"]] += Decimal(row["share_fraction"])
        primaries[row["client_number"]] += row["is_primary"] == "true"

    assert dict(shares) == dict.fromkeys(clients, Decimal("1.000000"))
    assert dict(primaries) == dict.fromkeys(clients, 1), "exactly one primary party each"


# --------------------------------------------------------------------------- #
# Unmistakably not real
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("column", "pattern", "what"),
    [
        ("email", _EMAIL, "an unresolvable example.invalid address"),
        ("phone", _PHONE, "a number in the 555-01xx block reserved for fiction"),
    ],
)
def test_client_contact_details_cannot_reach_a_real_person(
    column: str, pattern: re.Pattern[str], what: str
) -> None:
    """The guard that fails before the commit does.

    Not a style preference. This bundle lives in a public history for as long as
    the repository does, and the realistic way real data gets in is somebody
    pasting a row "just to reproduce a bug" and forgetting.
    """
    for row in rows("clients"):
        assert pattern.match(row[column]), f"{row['client_number']}.{column} is not {what}"


def test_identity_documents_are_visibly_placeholders() -> None:
    """The most sensitive fields in the contract, held to the strictest shape."""
    for row in rows("client_parties"):
        assert _IDENTITY.match(row["identity_document_number"]), row["client_number"]
        assert _TAX.match(row["tax_id"]), row["client_number"]
        assert row["name_as_identification"].startswith("Sample "), row["client_number"]


def test_no_cell_in_the_fixture_is_a_formula() -> None:
    """Not the same as "no cell needs escaping", which is what this asked first.

    That first version failed on ``+1-555-0101``. A telephone number in
    international format starts with ``+``, which is a formula leader, so
    ``spreadsheet_safe`` guards it — correctly, because Excel reads
    ``+1-555-0101`` as a formula and renders ``#NAME?``. **Every international
    phone number in this system will be escaped with a leading apostrophe**, and
    that is the design rather than a defect; it is recorded here so nobody
    "fixes" it later.

    The property that actually matters is that no cell is an *attack*: nothing
    leads with ``=`` or ``@``, and nothing hides a leader behind whitespace that
    Excel strips before it decides. Leading ``+`` and ``-`` are legitimate —
    phone numbers and negative money — and are exactly the case ``is_number``
    and the guard were written to tell apart.
    """
    for name in import_order():
        for number, row in enumerate(rows(name), start=2):
            for column, cell in row.items():
                where = f"{name}.csv row {number} {column}={cell!r}"
                assert not cell.startswith(("=", "@", "\t", "\r")), where
                assert cell == cell.strip() or not cell.strip().startswith(("=", "@")), where


def test_a_phone_number_is_escaped_rather_than_executed() -> None:
    """The behaviour the test above discovered, asserted rather than assumed.

    If ``spreadsheet_safe`` ever stopped guarding a leading ``+``, a reject
    report containing one would hand Excel something to evaluate. Asserted on
    the fixture's own data so the two cannot drift.
    """
    phone = rows("clients")[0]["phone"]
    assert phone.startswith("+")
    assert spreadsheet_safe(phone) == "'" + phone, "guarded, not executed, not dropped"


# --------------------------------------------------------------------------- #
# It survives the machinery
# --------------------------------------------------------------------------- #


def test_the_synthetic_bundle_seals_and_preflights_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], project_id: str
) -> None:
    """Both halves, end to end, on the committed files.

    The manifest is written to a temporary directory rather than beside the
    bundle: a sealed manifest carries hashes, and committing one would mean
    every edit to a fixture row silently invalidated a file in the repository.

    This is not a trial migration. It is the machinery, exercised.
    """
    names = sorted(f"{name}.csv" for name in import_order())
    declaration = tmp_path / "declaration.json"
    declaration.write_text(
        json.dumps(
            {
                "batch_id": str(uuid.uuid4()),
                "project_code": PROJECT_CODE,
                "source_system": "Synthetic fixture — no source system",
                "extracted_at": datetime(2026, 9, 5, 6, 0, tzinfo=UTC).isoformat(),
                "cutover_date": date(2026, 9, 30).isoformat(),
                "expected_currencies": [CURRENCY],
                "operator": "A. Operator",
                "reason": "exercise the machinery on synthetic data",
                "contract_version": CONTRACT_VERSION,
            }
        ),
        encoding="utf-8",
    )
    manifest = seal(load(declaration), directory=BUNDLE, names=names)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest.as_dict()), encoding="utf-8")

    code = main(
        ["--json", "preflight", "--bundle", str(BUNDLE), "--manifest", str(path), "--target"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "PASS", payload["checks"]
    assert code == 0
    assert len(manifest.files) == len(names)
