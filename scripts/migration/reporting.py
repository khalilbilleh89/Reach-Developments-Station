"""Report writers for the cutover: JSON for machines, CSV for the operator.

Two audiences and two formats, and the split matters. The JSON artifacts are
the evidence chain — a batch's validation result, its apply result, its
reconciliation — and they are what gets retained and re-read. The CSV artifacts
exist so a person can sort a thousand rejects in a spreadsheet and work through
them, which is the only realistic way that job gets done.

That second audience is the whole reason this module is careful. A reject
report is written *from source-controlled text*: the values in it were typed by
somebody into the system we are migrating away from. Handing that text to Excel
without thinking is how a migration report becomes a code-execution vector
against the finance team that opens it.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

#: Characters that make a spreadsheet treat a cell as a formula rather than as
#: text. ``=`` and ``@`` are unambiguous. ``+`` and ``-`` are the interesting
#: ones and are handled below. The two control characters are here because Excel
#: strips leading whitespace before deciding, so a tab or carriage return in
#: front of an ``=`` sneaks a formula past a naive check.
FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")

#: Prefixed to a cell that would otherwise be read as a formula. Excel and
#: LibreOffice both treat a leading apostrophe as "the rest of this is text" and
#: do not display it. It *is* visible to a CSV parser, which is why the JSON
#: artifacts rather than these files are the machine-readable truth.
TEXT_GUARD = "'"


def is_number(value: str) -> bool:
    """Whether a cell is a plain number, and therefore safe as it stands.

    This is what keeps the guard from corrupting the report it is protecting.
    Money in a reject report is routinely negative — a reversal, a credit, an
    over-allocation — and ``-1500.00`` starts with a character on the dangerous
    list. Escaping it would put an apostrophe in front of every negative figure
    in the file and turn a column of numbers into a column of text that will
    not sum. A value that parses as a number cannot also be a formula, so
    parsing is the discriminator rather than a guess about intent.
    """
    try:
        Decimal(value)
    except (InvalidOperation, ValueError):
        return False
    return True


def spreadsheet_safe(value: object) -> str:
    """One cell, rendered so a spreadsheet will not execute it.

    Returns text, always. The guard is added only when the cell both starts
    with a dangerous character and is not a number, so the common cases —
    references, codes, reasons, amounts — pass through untouched and the report
    still reads like the data it describes.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal | int):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()

    text = str(value)
    if not text:
        return ""
    if text.startswith(FORMULA_LEADERS) and not is_number(text):
        return TEXT_GUARD + text
    return text


def write_csv(path: Path, *, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> int:
    """Write a report a person will open in Excel. Returns the row count.

    Every value goes through :func:`spreadsheet_safe`. Columns are explicit
    rather than inferred from the first row, so a row that happens to be
    missing a key produces an empty cell instead of silently reshaping the file
    from that point down.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([spreadsheet_safe(column) for column in columns])
        for row in rows:
            writer.writerow([spreadsheet_safe(row.get(column)) for column in columns])
            written += 1
    return written


def _plain(value: object) -> object:
    """Render a value JSON can hold without losing what it meant.

    ``Decimal`` becomes a string, never a float. A cutover report that said
    ``249999.99999999997`` where the ledger says ``250000.00`` would be worse
    than no report, and every money figure in this package is a ``Decimal``.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        raise TypeError(
            "A set has no order, so a report containing one is not the diffable evidence this "
            "writer claims to produce: two runs of the same batch could serialise the same "
            "finding differently. Sort it into a list at the point where the ordering is a "
            "decision somebody made, rather than here where it would be a coin toss."
        )
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one of the evidence artifacts.

    Sorted keys and a trailing newline so two runs of the same batch produce
    files a person can diff, which is how "did anything change between the
    trial and the real thing?" gets answered.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_plain(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class Reject:
    """One row the cutover refused, described so somebody can go and fix it.

    Deliberately narrow. Everything here is either a locator or a code — there
    is no field that could carry a buyer's name, an email address, a passport
    number or a bank reference, because a reject report gets mailed around and
    left in a shared folder. The row number and the business reference are
    enough to find the row in the source; the source is where the identity
    lives, and it stays there.

    **No field on this record echoes source content.** An earlier version
    carried the value that failed — the date that would not parse, the code that
    was not found — which reads as helpful and is not yet defensible: deciding
    which fields are safe to quote needs the canonical intake contract to say
    which fields can hold identity, and that contract does not exist until the
    real source does. "The supplied value where safe" is the right long-term
    rule; today nothing can prove *where safe*, so nothing is quoted.

    What survives is enough to act on: the file and row locate it, the reference
    names it in the operator's own vocabulary, and the code says what is wrong.
    Fixing the row means opening the source, which is where the value already is.
    """

    #: The canonical intake file the row came from, e.g. ``sales.csv``.
    source_file: str
    #: 1-based row number within that file, header excluded. For navigation
    #: only: a spreadsheet row is not an identity and is never used as one.
    row: int
    #: The business key that identifies the record — an SPA number, a unit
    #: reference, a receipt number. ``None`` when the row is too broken to have
    #: one, which is itself worth seeing.
    #:
    #: This is the one field whose content comes from the source, and it is a
    #: key rather than a value. Keeping it free of identity is the mapping's
    #: job, not this record's: a source that keyed its contracts by buyer name
    #: is a mapping decision to refuse, and there is no mapping yet.
    reference: str | None
    #: The column that failed, or ``None`` when the whole row is the problem.
    field: str | None
    #: A stable machine-readable code, e.g. ``UNKNOWN_UNIT``. Codes are how a
    #: thousand rejects become five problems.
    code: str
    #: One sentence a person can act on, in the vocabulary of the business
    #: rather than of the database.
    reason: str
    #: ``blocking`` stops the apply. ``warning`` does not.
    severity: str = "blocking"

    def as_row(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "row": self.row,
            "reference": self.reference,
            "field": self.field,
            "code": self.code,
            "reason": self.reason,
            "severity": self.severity,
        }


#: The reject report's columns, in the order an operator reads them: where it
#: is, what it is, what is wrong.
REJECT_COLUMNS: tuple[str, ...] = (
    "source_file",
    "row",
    "reference",
    "field",
    "code",
    "reason",
    "severity",
)


def write_rejects(path: Path, rejects: Sequence[Reject]) -> int:
    """Write the reject report. Returns the number of rows written."""
    return write_csv(path, columns=REJECT_COLUMNS, rows=[reject.as_row() for reject in rejects])
