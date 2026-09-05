"""A log line that cannot carry somebody's identity, proved rather than intended.

The threat is mundane. A cutover fails on row 147 at two in the morning, the
obvious diagnostic is the row, and the row has a buyer's name and passport
number in it. Logged once, it is then in a log aggregator, a terminal
scrollback, a screenshot in a chat thread and a support ticket — and nobody
decided any of that.

Every guard below is about the shape of the mechanism rather than the good
intentions of its callers, because the caller that leaks is always the one
written in a hurry.
"""

from __future__ import annotations

import pytest

from scripts.migration.journal import (
    EXCLUDED_FIELDS,
    FIELDS,
    MAX_VALUE,
    UnsafeLogLine,
    line,
)
from scripts.migration.reporting import REJECT_COLUMNS


def test_a_rejection_reads_the_way_the_brief_asks_for() -> None:
    """The worked example, so the format is a fact rather than a description."""
    assert line(
        batch="6f1cadc0",
        action="validate",
        source_file="units.csv",
        row=147,
        reference="SPA-00147",
        status="rejected",
        code="UNKNOWN_UNIT",
    ) == (
        "source_file=units.csv row=147 reference=SPA-00147 code=UNKNOWN_UNIT "
        "batch=6f1cadc0 action=validate status=rejected"
    )


def test_the_order_is_the_allowlists_not_the_callers() -> None:
    """Two lines about one thing read the same, whatever order they were typed.

    A log people grep is a log whose shape has to be stable; a keyword order
    change is not supposed to be a format change.
    """
    assert line(code="X", row=1) == line(row=1, code="X")


def test_a_field_that_does_not_apply_is_absent_not_the_word_none() -> None:
    assert line(code="X", reference=None) == "code=X"
    assert "reference" not in line(code="X", reference=None)


# --------------------------------------------------------------------------- #
# Only what somebody allowed
# --------------------------------------------------------------------------- #


def test_an_unlisted_field_is_refused_rather_than_dropped() -> None:
    """Fail closed, and loudly.

    A denylist lets through whichever field is added next, and that is the one
    carrying the name. Dropping it silently is barely better: the operator reads
    a line that looks complete and never learns what was withheld.
    """
    with pytest.raises(UnsafeLogLine, match="buyer_name"):
        line(code="X", buyer_name="Sample Buyer Alpha")


@pytest.mark.parametrize("field", sorted(EXCLUDED_FIELDS))
def test_the_fields_identity_travels_in_are_not_loggable(field: str) -> None:
    """Named individually so removing one is a visible decision.

    ``reason`` is the interesting entry: it is a legitimate column on a reject
    report — a sentence for a person — and free text is exactly where a value
    quoted back out of the source would ride. The report may carry it, because
    that file is written once and handled deliberately. A log line is copied,
    pasted and shipped to wherever logs go.
    """
    assert field not in FIELDS
    with pytest.raises(UnsafeLogLine):
        line(**{field: "anything"})


def test_a_rejection_can_be_logged_without_reaching_for_a_field_that_is_missing() -> None:
    """The pressure that would otherwise produce a hand-rolled format string.

    If a log line could say less than a reject report about *where* a rejection
    happened, somebody would format their own line, and their own line has no
    allowlist. Every locator on the record is loggable; only ``reason`` is not.
    """
    loggable = set(REJECT_COLUMNS) & set(FIELDS)
    assert set(REJECT_COLUMNS) - loggable == {"reason"}


# --------------------------------------------------------------------------- #
# Identifiers, not prose
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "why"),
    [
        ("Sample Buyer Alpha", "a name has spaces"),
        ("alpha@example.invalid", "an email address has an @"),
        ("row 147\ncode=OK batch=forged", "a newline forges a second entry"),
        ("carriage\rreturn", "so does a carriage return"),
        ('quote"inside', "a quote breaks a parser reading the line back"),
        ("key=value", "an equals sign fabricates a second field"),
    ],
)
def test_a_value_that_is_not_an_identifier_is_refused(value: str, why: str) -> None:
    """The allowlist protects the *keys*; this protects the values.

    An allowlisted field is still a hole if a caller puts a name in it — and
    ``reference`` is exactly the field somebody would reach for when the unit
    number is not to hand. Every field here names a code, a locator, a count or
    a status, and none of those contains a space, an ``@``, or a line break.
    """
    with pytest.raises(UnsafeLogLine):
        line(reference=value)


def test_prose_is_refused_at_a_length_that_does_not_depend_on_the_constant() -> None:
    """Written first as ``"x" * (MAX_VALUE + 1)``, which proved nothing.

    That version is relative to the very bound it is meant to pin: raise
    ``MAX_VALUE`` to a hundred thousand and it still generates a string one
    character longer, still raises, still passes. The falsification found it —
    the mutation that widened the bound left every test green.

    So the lengths here are absolute and chosen for what they represent. Two
    hundred characters is an address or a source row; sixty-four is the longest
    identifier in this schema (``VARCHAR(64)`` on ``units.unit_reference`` among
    others) and has to keep working.
    """
    with pytest.raises(UnsafeLogLine, match="characters"):
        line(reference="x" * 200)
    assert line(reference="x" * 64) == "reference=" + "x" * 64


def test_the_bound_is_identifier_sized_rather_than_document_sized() -> None:
    """Pins the constant itself, since no behavioural test can.

    A bound wide enough to admit a source row admits a source row, and the
    module's whole claim is that a value is an identifier rather than prose.
    """
    assert MAX_VALUE <= 128, "a bound this wide admits prose, which is what carries identity"
    assert MAX_VALUE >= 64, "the schema's longest identifier column is VARCHAR(64)"


def test_an_empty_value_is_refused_rather_than_written_blank() -> None:
    """``reference=`` reads as a value nobody recorded, not one that is absent."""
    with pytest.raises(UnsafeLogLine, match="empty"):
        line(reference="")


def test_the_refusal_names_the_field_so_it_can_be_fixed() -> None:
    """A refusal nobody can act on gets worked around."""
    with pytest.raises(UnsafeLogLine, match="reference"):
        line(code="OK", reference="Sample Buyer Alpha")


def test_numbers_and_booleans_survive_intact() -> None:
    """Counts and flags are the ordinary case and must not need stringifying."""
    assert line(row=147, count=1500, rejected=3) == "row=147 count=1500 rejected=3"
    assert line(status="ok", severity="error") == "severity=error status=ok"


def test_a_real_source_row_cannot_be_logged_whole() -> None:
    """The failure this module exists for, attempted directly.

    Not a formality: this is precisely what somebody writes at two in the
    morning when the reject code is not enough to see what went wrong.
    """
    row = {
        "unit_reference": "GB-P1-B1-G-01",
        "display_name": "Sample Buyer Alpha",
        "email": "alpha@example.invalid",
        "identity_document_number": "ID-SAMPLE-0001",
    }
    with pytest.raises(UnsafeLogLine):
        line(reference=str(row))
    with pytest.raises(UnsafeLogLine):
        line(code="BAD_ROW", email=row["email"])
