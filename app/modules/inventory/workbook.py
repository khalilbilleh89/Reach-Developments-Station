"""The operator's inventory workbook: one ``.xlsx``, four object sheets.

A project team is handed a file, not a column list. The CSV importer that came
before this is more capable and stays available, but it is one flat unit-shaped
table: a phase exists in it only because some unit row mentioned it, so a team
cannot lay out a development's structure before deciding what is on floor
three. This workbook can, because Phases, Buildings and Floors are sheets of
their own.

**One domain truth, two input adapters.** Nothing here decides whether a code is
unique, whether an actor may see a phase, whether a reference value exists,
whether a unit may be released, what gets audited, or when the transaction
commits. Unit rows go through :func:`import_service.parse_rows` — the same
function the CSV calls, reached through the same seam — and hierarchy rows go
through the same ``inventory.service`` calls the manual forms use. This module
knows about *workbook structure* and nothing else.

**A spreadsheet is data.** Nothing here evaluates a cell. A formula is refused
outright rather than resolved: openpyxl is opened with ``data_only=False`` so a
formula arrives as its text, and the cached value Excel left behind is never
read. "``=1+1``" is a workbook this importer declines, not the number two. The
archive is checked before the content — macros, encryption, a malformed package
and a decompression bomb are all refused with a sentence saying which.

**The version is written down, not guessed.** ``Instructions!B1`` carries
``inventory_structure_v1``. It is not inferred from the filename, because a
filename survives nothing. When PR-V2-03 extends what a Unit row may say, an old
workbook keeps meaning exactly what it meant.
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.cell.read_only import ReadOnlyCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory import import_service, service
from app.modules.inventory.models import (
    ASSET_CLASSES,
    ENTITY_IMPORT,
    PHASE_STATUSES,
    Building,
    Floor,
    Phase,
)
from app.modules.inventory.permissions import (
    require_inventory_structure_writer,
    require_project_configurer,
)
from app.modules.inventory.schemas import (
    BuildingCreateRequest,
    FloorCreateRequest,
    PhaseCreateRequest,
)
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project

# --------------------------------------------------------------------------- #
# The contract
# --------------------------------------------------------------------------- #

#: What this parser understands. Machine-readable, and read from a cell rather
#: than from the filename: a downloaded file is renamed, copied and mailed on,
#: and none of that may change what its columns mean.
TEMPLATE_VERSION = "inventory_structure_v1"
SUPPORTED_VERSIONS = frozenset({TEMPLATE_VERSION})

SHEET_INSTRUCTIONS = "Instructions"
SHEET_PHASES = "Phases"
SHEET_BUILDINGS = "Buildings"
SHEET_FLOORS = "Floors"
SHEET_UNITS = "Units"

#: Every sheet the workbook must still have when it comes back.
REQUIRED_SHEETS = (SHEET_INSTRUCTIONS, SHEET_PHASES, SHEET_BUILDINGS, SHEET_FLOORS, SHEET_UNITS)

#: Where the version lives, and the label beside it so a person knows what it is.
VERSION_LABEL_CELL = "A1"
VERSION_CELL = "B1"
VERSION_LABEL = "Template version"

#: ``(column, required)`` per sheet, in the order the template writes them.
PHASE_COLUMNS: tuple[tuple[str, bool], ...] = (
    ("phase_code", True),
    ("phase_name", True),
    ("sequence", False),
    ("status", False),
    ("planned_start", False),
    ("planned_completion", False),
    ("notes", False),
)
BUILDING_COLUMNS: tuple[tuple[str, bool], ...] = (
    ("phase_code", True),
    ("building_code", True),
    ("building_name", True),
    ("zone", False),
    ("block", False),
    ("entrance_wing", False),
    ("sequence", False),
)
FLOOR_COLUMNS: tuple[tuple[str, bool], ...] = (
    ("phase_code", True),
    ("building_code", True),
    ("floor_code", True),
    ("floor_label", True),
    ("level_number", False),
    ("sequence", False),
)
#: Deliberately a subset of what a Unit is. This workbook loads structure; the
#: physical Unit master — internal area, balcony, terrace, parking, storage —
#: is PR-V2-03's, and putting its columns here now would fix their meaning
#: before that design exists. Every name is one the CSV importer already knows,
#: so the Units sheet needs no vocabulary of its own.
UNIT_COLUMNS: tuple[tuple[str, bool], ...] = (
    ("phase_code", True),
    ("building_code", True),
    ("floor_code", True),
    ("unit_number", True),
    ("unit_reference", True),
    ("sequence", False),
    ("asset_class", True),
    ("unit_type_code", False),
    ("bedrooms", False),
    ("bathrooms", False),
)

SHEET_COLUMNS: dict[str, tuple[tuple[str, bool], ...]] = {
    SHEET_PHASES: PHASE_COLUMNS,
    SHEET_BUILDINGS: BUILDING_COLUMNS,
    SHEET_FLOORS: FLOOR_COLUMNS,
    SHEET_UNITS: UNIT_COLUMNS,
}

#: The one date format the workbook documents and accepts as text. A real date
#: cell is read as a date and never reformatted; text is read as written, and
#: "03/04/2026" is refused rather than guessed at, because it is the third of
#: April in one country and the fourth of March in another.
DATE_FORMAT = "YYYY-MM-DD"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: The upload bound, and why it is not simply the CSV's.
#:
#: A workbook is a ZIP, so the 5 MB an operator sees is not the size this
#: process has to hold. The compressed bound stays at the CSV's 5 MB because
#: the operator's mental model should not need two numbers — a 247-unit
#: workbook is around 20 KB, so 5 MB is already three orders of magnitude of
#: headroom. The bound that actually matters is the second one: a few hundred
#: kilobytes of ZIP can expand to gigabytes, and no legitimate inventory
#: workbook comes anywhere near 64 MB unpacked.
MAX_BYTES = import_service.MAX_BYTES
MAX_UNCOMPRESSED = 64 * 1024 * 1024

#: How much of one member is held at a time while it is being counted.
_READ_CHUNK = 256 * 1024

#: Rows per sheet. Units reuses the CSV importer's bound so one file cannot
#: load more units through the workbook than through the CSV.
MAX_UNIT_ROWS = import_service.MAX_ROWS
MAX_STRUCTURE_ROWS = 2000

HEADER_ROW = 1
FIRST_DATA_ROW = 2

#: Request-model field name -> this sheet's column heading. The models are the
#: authoritative home for lengths and minimums; these maps only translate where
#: to point the operator.
_PHASE_FIELD_COLUMNS = {"code": "phase_code", "name": "phase_name"}
_BUILDING_FIELD_COLUMNS = {"code": "building_code", "name": "building_name"}
_FLOOR_FIELD_COLUMNS = {"code": "floor_code", "label": "floor_label"}

#: A stand-in parent for contract validation only. The request models require a
#: parent identifier; at validate time the real parent may be a row further up
#: this same workbook and have no identifier yet. Parent *resolution* is checked
#: separately and precisely — this placeholder only lets the model judge the
#: fields it owns.
_UNRESOLVED_PARENT = uuid.UUID(int=0)

IMPORT_MODES = import_service.IMPORT_MODES


# --------------------------------------------------------------------------- #
# Reading cells without executing anything
# --------------------------------------------------------------------------- #


#: The file is not a workbook this importer will open at all — distinct from a
#: validation issue, which names a cell an operator can fix. A macro-enabled
#: workbook has no row 24 to report against.
#:
#: An alias rather than a subclass, deliberately. ``app.main`` maps service
#: errors to statuses with ``dict.get(type(exc))`` — an *exact* type lookup, not
#: an MRO walk — so a subclass of ``ValidationError`` silently stops being a 422
#: and becomes the 400 fallback. That was found here by a test asserting the
#: status of a refused workbook, and the name is kept so this module can still
#: say what it means without the type system quietly changing the answer.
WorkbookRefused = ValidationError


def _refuse(message: str) -> ValidationError:
    return WorkbookRefused(message)


def _is_formula(cell: Cell | ReadOnlyCell) -> bool:
    """Whether this cell is a formula, by any of the ways one can appear.

    ``data_type == "f"`` is openpyxl's answer for an ordinary formula. An array
    or shared formula arrives as an object rather than a string, and a cell
    written by something other than Excel can carry the text without the type.
    Any of the three is refused; none of the three is evaluated.
    """
    if getattr(cell, "data_type", None) == "f":
        return True
    value = cell.value
    if type(value).__name__ in {"ArrayFormula", "DataTableFormula"}:
        return True
    return isinstance(value, str) and value.startswith("=")


def _text(value: object) -> str:
    """One cell as the text the CSV importer would have been given.

    A date cell becomes its ISO date rather than a timestamp, because a
    spreadsheet stores "2026-04-20" as midnight on that day and an operator did
    not type a time. A whole number typed into a General cell arrives as a
    float, and "3.0" is not a bedroom count anybody wrote.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _archive_is_safe(body: bytes) -> None:
    """Refuse the package before anything inside it is decompressed.

    Order is the security property here, not the set of checks. An earlier
    version called ``ZipFile.testzip()`` first and compared the uncompressed
    size afterwards — and ``testzip`` decompresses every member to verify its
    CRC, so the bomb was expanded in order to decide whether it was too big to
    expand. The PR describing it claimed the opposite. It is now:

    1. the compressed bound, on bytes already in hand;
    2. the central directory, which is metadata and costs nothing;
    3. the declared uncompressed total, refused before any member is opened;
    4. macros and the shape of the package;
    5. only then, reading members — and never unboundedly.

    Step three is the gate that matters, and it is enough: ``ZipExtFile`` bounds
    each read by the declared ``file_size`` and then raises on the CRC
    mismatch, so an archive that understates itself truncates and fails rather
    than over-delivering — verified against CPython 3.11 rather than assumed.
    A bomb therefore has to declare its size to be readable at all, and the
    central directory is where it is refused.

    Step five replaces ``testzip`` rather than restoring it: the same CRC
    verification, but counted against the same bound as it goes, so nothing
    here can read more than the directory was judged on.
    """
    if not body:
        raise _refuse("That file is empty.")
    if len(body) > MAX_BYTES:
        raise _refuse(
            f"That file is larger than the {MAX_BYTES // (1024 * 1024)} MB limit for an "
            "inventory workbook."
        )
    if body[:2] == b"\xd0\xcf":
        raise _refuse(
            "That workbook is password-protected or in the older .xls format. Save it as "
            "an unprotected .xlsx and try again."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            declared = sum(entry.file_size for entry in entries)
            if declared > MAX_UNCOMPRESSED:
                raise _refuse(
                    "That workbook expands to far more data than an inventory load needs."
                )
            names = {entry.filename for entry in entries}
            if any(name.startswith("xl/vbaProject") for name in names):
                raise _refuse(
                    "That workbook contains macros. Save it as a plain .xlsx — an inventory "
                    "import reads data and never runs code."
                )
            if "xl/workbook.xml" not in names:
                raise _refuse("That file is not a readable .xlsx workbook.")
            _read_within_bounds(archive, entries)
    except zipfile.BadZipFile as caught:
        raise _refuse(
            "That file is not a readable .xlsx workbook. Download the template and fill "
            "that in rather than converting another format."
        ) from caught


def _read_within_bounds(archive: zipfile.ZipFile, entries: list[zipfile.ZipInfo]) -> None:
    """Read every member through the uncompressed bound, verifying it on the way.

    The replacement for ``testzip``: same CRC verification, but the bytes are
    counted as they arrive, so an archive whose central directory understates
    what it holds is refused part-way through rather than after.
    """
    read = 0
    for entry in entries:
        with archive.open(entry) as member:
            while chunk := member.read(_READ_CHUNK):
                read += len(chunk)
                if read > MAX_UNCOMPRESSED:
                    raise _refuse(
                        "That workbook expands to far more data than an inventory load needs."
                    )


def _load(body: bytes) -> Workbook:
    """Open the workbook read-only, with formulas left as text.

    ``data_only=False`` is the load-bearing argument. With ``True``, openpyxl
    hands back the value Excel cached the last time it calculated — a number
    this system never computed, from a formula nobody here has seen, which
    would then be imported as though an operator had typed it.
    """
    _archive_is_safe(body)
    try:
        return load_workbook(
            io.BytesIO(body), read_only=True, data_only=False, keep_vba=False, rich_text=False
        )
    except _RefusedTypes as caught:  # pragma: no cover - openpyxl raises many shapes
        raise _refuse("That file is not a readable .xlsx workbook.") from caught


_RefusedTypes = (zipfile.BadZipFile, KeyError, ValueError, TypeError)


# --------------------------------------------------------------------------- #
# The template
# --------------------------------------------------------------------------- #

_HEADER_FILL = PatternFill("solid", fgColor="1F2933")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_REQUIRED_FONT = Font(color="B42318", bold=True)
_TITLE_FONT = Font(bold=True, size=13)
_THIN = Side(style="thin", color="D9DDE3")
_BORDER = Border(bottom=_THIN)

_WIDTHS = {
    "notes": 46,
    "phase_name": 28,
    "building_name": 28,
    "floor_label": 24,
    "unit_reference": 20,
    "planned_start": 16,
    "planned_completion": 20,
    "entrance_wing": 16,
    "unit_type_code": 18,
    "level_number": 14,
}

_INSTRUCTIONS: tuple[tuple[str, str], ...] = (
    (
        "What this workbook is",
        "The exact file this project's inventory import reads. Fill in the sheets you "
        "need and upload it — Phases, Buildings, Floors and Units, in that order of "
        "dependency.",
    ),
    (
        "Do not rename anything",
        "Sheet names and header rows are the contract. A renamed sheet or column is "
        "refused rather than guessed at.",
    ),
    (
        "Codes are identity",
        "phase_code, building_code and floor_code are how rows find their parent, here "
        "and in the system. They are stable: a code is not renamed later.",
    ),
    (
        "Parents must exist",
        "A building's phase_code must already exist in the project or be a row on the "
        "Phases sheet of this same workbook. The same holds for floors and units.",
    ),
    (
        "Building codes are per phase",
        "B1 in Phase 1 and B1 in Phase 2 are different buildings. Floor codes are per "
        "building in the same way.",
    ),
    ("Dates", f"{DATE_FORMAT}, or a real date cell. No other format is accepted."),
    (
        "Required columns",
        "Marked in the header. An optional column may be left blank; do not delete it.",
    ),
    ("Blank cells", "A blank optional cell means 'not stated', and nothing is written for it."),
    (
        "Create and upsert",
        "Create refuses a code that already exists. Upsert updates the record that code "
        "names. Codes are never changed by an import, and a building never changes phase.",
    ),
    (
        "Units are created, not updated",
        "A unit reference can be edited in the system, so it is not identity — matching "
        "on it would rewrite whichever unit currently carries the text. Update units "
        "individually, or through the advanced CSV import where the unit's identifier is "
        "explicit.",
    ),
    ("Asset classes", ", ".join(ASSET_CLASSES)),
    ("Phase statuses", ", ".join(PHASE_STATUSES)),
    (
        "Nothing is written until you apply",
        "Validate reads the workbook and reports what would happen. Apply reads the file "
        "again from scratch and writes the whole workbook or none of it.",
    ),
    (
        "Formulas",
        "A cell containing a formula is refused. Paste values rather than references to "
        "another sheet.",
    ),
)


def template() -> bytes:
    """Build the workbook an operator downloads.

    Blank apart from the header and the instructions. Seeding it with the
    project's existing phases would make it look like a two-way sync, and the
    first operator to delete a row from a "template" that arrived full would
    expect something to be deleted.
    """
    book = Workbook()
    notes = book.active
    notes.title = SHEET_INSTRUCTIONS

    notes[VERSION_LABEL_CELL] = VERSION_LABEL
    notes[VERSION_LABEL_CELL].font = Font(bold=True)
    notes[VERSION_CELL] = TEMPLATE_VERSION
    notes["C1"] = "Do not edit this cell — the importer reads it to know what these columns mean."
    notes["A3"] = "Reach inventory workbook"
    notes["A3"].font = _TITLE_FONT

    row = 5
    for heading, body in _INSTRUCTIONS:
        notes.cell(row=row, column=1, value=heading).font = Font(bold=True)
        cell = notes.cell(row=row, column=2, value=body)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1
    notes.column_dimensions["A"].width = 30
    notes.column_dimensions["B"].width = 96
    notes.column_dimensions["C"].width = 20
    notes.freeze_panes = "A5"

    for sheet_name, columns in SHEET_COLUMNS.items():
        sheet = book.create_sheet(sheet_name)
        for position, (column, required) in enumerate(columns, start=1):
            cell = sheet.cell(row=HEADER_ROW, column=position, value=column)
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="center")
            letter = get_column_letter(position)
            sheet.column_dimensions[letter].width = _WIDTHS.get(column, max(len(column) + 4, 14))
            if required:
                # Marked in the header itself rather than on a second row: an
                # extra row is one more thing to delete by accident, and the
                # importer would then read "optional" as a data row.
                cell.font = Font(color="FFFFFF", bold=True, underline="single")
        sheet.freeze_panes = sheet.cell(row=FIRST_DATA_ROW, column=1).coordinate
        sheet.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(len(columns))}{HEADER_ROW}"

    notes.cell(row=row + 1, column=1, value="Required columns are underlined in each header row.")

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Reading a filled-in workbook
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class Declared:
    """One hierarchy record a workbook asks for, addressed by code.

    ``existing`` is the record the codes already name, if any: the parse
    resolves it once so the apply does not go looking again and reach a
    different answer.
    """

    sheet: str
    row: int
    codes: tuple[str, ...]
    fields: dict[str, Any]
    action: str
    existing: Phase | Building | Floor | None = None


@dataclass(slots=True)
class Structure:
    """Everything one workbook asked for, and everything wrong with it."""

    batch: import_service.Batch
    version: str | None = None
    phases: list[Declared] = field(default_factory=list)
    buildings: list[Declared] = field(default_factory=list)
    floors: list[Declared] = field(default_factory=list)
    #: Data rows read per sheet, whether or not they survived checking.
    rows_read: dict[str, int] = field(default_factory=dict)

    def counts(self, records: list[Declared]) -> dict[str, int]:
        return {
            "create": sum(1 for record in records if record.action == "create"),
            "update": sum(1 for record in records if record.action == "update"),
        }


def _read_sheet(
    book: Workbook, *, name: str, columns: tuple[tuple[str, bool], ...], limit: int
) -> list[tuple[int, dict[str, str]]]:
    """Every data row of one sheet, as text, with the header proved first.

    Read by column name rather than by position, exactly as ``csv.DictReader``
    reads the CSV: a workbook whose columns were dragged into a different order
    still means what it says, while a renamed or invented column is refused
    rather than silently read as something else.
    """
    sheet = book[name]
    header_cells = next(sheet.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW), ())
    for cell in header_cells:
        if _is_formula(cell):
            raise _refuse(f"The header of the {name} sheet contains a formula.")
    headers = [_text(cell.value) for cell in header_cells]
    while headers and headers[-1] == "":
        headers.pop()

    expected = [column for column, _ in columns]
    if sorted(headers) != sorted(expected):
        missing = sorted(set(expected) - set(headers))
        unknown = sorted(set(headers) - set(expected))
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unknown:
            detail.append("unexpected " + ", ".join(unknown))
        raise _refuse(
            f"The {name} sheet's header row does not match the template "
            f"({'; '.join(detail)}). Download the template again rather than editing the "
            "header."
        )
    if len(headers) != len(set(headers)):
        raise _refuse(f"The {name} sheet has the same column twice.")

    rows: list[tuple[int, dict[str, str]]] = []
    for cells in sheet.iter_rows(min_row=FIRST_DATA_ROW):
        number = cells[0].row if cells else 0
        values: dict[str, str] = {}
        for position, cell in enumerate(cells):
            if position >= len(headers):
                break
            if _is_formula(cell):
                raise _refuse(
                    f"{name} row {number}, column {headers[position]} contains a formula. "
                    "An inventory import reads data and never calculates it — paste the "
                    "value instead."
                )
            values[headers[position]] = _text(cell.value)
        if not any(values.values()):
            continue
        for column in headers:
            values.setdefault(column, "")
        rows.append((number, values))
        if len(rows) > limit:
            raise _refuse(f"The {name} sheet has more than the {limit} rows this import accepts.")
    return rows


def _int(batch: import_service.Batch, *, row: int, column: str, raw: str) -> int | None:
    if raw == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        batch.error(row, column, f"'{raw}' is not a whole number.")
        return None
    return value


def _iso_date(batch: import_service.Batch, *, row: int, column: str, raw: str) -> date | None:
    if raw == "":
        return None
    if not _ISO_DATE.match(raw):
        batch.error(row, column, f"'{raw}' is not a date. Use {DATE_FORMAT}.")
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        batch.error(row, column, f"'{raw}' is not a real date.")
        return None


def _required(
    batch: import_service.Batch,
    *,
    row: int,
    values: dict[str, str],
    columns: tuple[tuple[str, bool], ...],
) -> bool:
    complete = True
    for column, required in columns:
        if required and values.get(column, "") == "":
            batch.error(row, column, f"{column} is required.")
            complete = False
    return complete


def _through_the_request_contract(
    batch: import_service.Batch,
    *,
    row: int,
    model: type[BaseModel],
    payload: dict[str, Any],
    columns: dict[str, str],
) -> bool:
    """Judge one row by the request model the manual form is judged by.

    Lengths, minimums and the status vocabulary have an authoritative home in
    ``inventory.schemas``. Restating them here as a second dictionary of limits
    is how a workbook comes to accept a 300-character zone that the form
    refuses — and worse, how ``validate`` comes to report clean on a workbook
    ``apply`` will then reject.

    ``columns`` maps the model's field names to this sheet's column names, so
    the operator is sent to the cell rather than to a field they cannot see.
    """
    try:
        model.model_validate(payload)
    except PydanticValidationError as caught:
        for error in caught.errors():
            field = str(error["loc"][0]) if error["loc"] else None
            batch.error(row, columns.get(field or "", field), error["msg"])
        return False
    return True


def _domain_value(
    batch: import_service.Batch, *, row: int, column: str, call: Callable[[], str]
) -> str | None:
    """One code as the service's own normaliser returns it, or None if refused.

    The same function the apply path calls, so a value cannot pass validate and
    fail apply on a rule this module could have asked about.
    """
    try:
        return call()
    except ValidationError as caught:
        batch.error(row, column, caught.detail)
        return None


def _domain_allows(
    batch: import_service.Batch, *, row: int, column: str, call: Callable[[], None]
) -> bool:
    """Whether one of the service's own checks passes, reported as a cell."""
    try:
        call()
    except ValidationError as caught:
        batch.error(row, column, caught.detail)
        return False
    return True


def _duplicate(
    batch: import_service.Batch,
    *,
    row: int,
    column: str,
    key: tuple[str, ...],
    seen: dict[tuple[str, ...], int],
    what: str,
) -> bool:
    """Refuse a second row for the same record, identical or not.

    Two rows for one record is a mistake whichever way they disagree, and
    quietly keeping the last one means an operator's correction and their
    duplicate are indistinguishable.
    """
    if key in seen:
        batch.error(row, column, f"{what} is already declared on row {seen[key]} of this sheet.")
        return True
    seen[key] = row
    return False


def _existing_hierarchy(
    session: Session, *, project: Project, actor: ActorContext
) -> tuple[dict[str, Phase], dict[tuple[str, str], Building], dict[tuple[str, str, str], Floor]]:
    """What this actor can already see, keyed the way the workbook speaks.

    Read through the service's own list functions rather than a query of this
    module's own, so phase visibility is applied by the code that owns it. A
    phase an actor may not see is not in this map, and the database's unique
    indexes remain the final authority on what may be created.
    """
    phases = {
        phase.code: phase for phase in service.list_phases(session, project=project, actor=actor)
    }
    by_id = {phase.id: phase.code for phase in phases.values()}
    buildings: dict[tuple[str, str], Building] = {}
    for building in service.list_buildings(session, project=project, actor=actor):
        phase_code = by_id.get(building.phase_id)
        if phase_code is not None:
            buildings[(phase_code, building.code)] = building
    building_ids = {building.id: codes for codes, building in buildings.items()}
    floors: dict[tuple[str, str, str], Floor] = {}
    for floor in service.list_floors(session, project=project, actor=actor):
        codes = building_ids.get(floor.building_id)
        if codes is not None:
            floors[(*codes, floor.code)] = floor
    return phases, buildings, floors


def _action_for(
    batch: import_service.Batch,
    *,
    row: int,
    column: str,
    mode: str,
    existing: object | None,
    what: str,
) -> str | None:
    """Whether this row creates or updates, and whether the mode allows it."""
    if existing is None:
        return "create"
    if mode == "create":
        batch.error(
            row,
            column,
            f"{what} already exists. This import is in create mode; use upsert to update it.",
        )
        return None
    return "update"


def _read_phases(
    structure: Structure,
    *,
    rows: list[tuple[int, dict[str, str]]],
    mode: str,
    existing: dict[str, Phase],
) -> None:
    batch = structure.batch
    seen: dict[tuple[str, ...], int] = {}
    for row, values in rows:
        if not _required(batch, row=row, values=values, columns=PHASE_COLUMNS):
            continue
        code = _domain_value(
            batch,
            row=row,
            column="phase_code",
            call=lambda raw=values["phase_code"]: service.normalize_code(raw, label="A phase code"),
        )
        if code is None:
            continue
        if _duplicate(
            batch, row=row, column="phase_code", key=(code,), seen=seen, what=f"Phase '{code}'"
        ):
            continue
        fields: dict[str, Any] = {"code": code, "name": values["phase_name"]}
        sequence = _int(batch, row=row, column="sequence", raw=values["sequence"])
        if sequence is not None:
            fields["sequence"] = sequence
        if values["status"]:
            fields["status"] = values["status"]
        for column in ("planned_start", "planned_completion"):
            parsed = _iso_date(batch, row=row, column=column, raw=values[column])
            if parsed is not None:
                fields[column] = parsed
        if values["notes"]:
            fields["notes"] = values["notes"]
        if not _through_the_request_contract(
            batch, row=row, model=PhaseCreateRequest, payload=fields, columns=_PHASE_FIELD_COLUMNS
        ):
            continue
        if not _domain_allows(
            batch,
            row=row,
            column="planned_completion",
            call=lambda dates=fields: service.require_phase_dates_ordered(
                dates.get("planned_start"), dates.get("planned_completion")
            ),
        ):
            continue
        action = _action_for(
            batch,
            row=row,
            column="phase_code",
            mode=mode,
            existing=existing.get(code),
            what=f"Phase '{code}'",
        )
        if action is None:
            continue
        structure.phases.append(
            Declared(SHEET_PHASES, row, (code,), fields, action, existing.get(code))
        )


def _read_buildings(
    structure: Structure,
    *,
    rows: list[tuple[int, dict[str, str]]],
    mode: str,
    phases: dict[str, Phase],
    existing: dict[tuple[str, str], Building],
) -> None:
    batch = structure.batch
    declared_phases = {record.codes[0] for record in structure.phases}
    seen: dict[tuple[str, ...], int] = {}
    for row, values in rows:
        if not _required(batch, row=row, values=values, columns=BUILDING_COLUMNS):
            continue
        phase_code = _domain_value(
            batch,
            row=row,
            column="phase_code",
            call=lambda raw=values["phase_code"]: service.normalize_code(raw, label="A phase code"),
        )
        code = _domain_value(
            batch,
            row=row,
            column="building_code",
            call=lambda raw=values["building_code"]: service.normalize_code(
                raw, label="A building code"
            ),
        )
        if phase_code is None or code is None:
            continue
        if _duplicate(
            batch,
            row=row,
            column="building_code",
            key=(phase_code, code),
            seen=seen,
            what=f"Building '{code}' in phase '{phase_code}'",
        ):
            continue
        parent = phases.get(phase_code)
        if parent is None and phase_code not in declared_phases:
            batch.error(
                row,
                "phase_code",
                f"Phase '{phase_code}' does not exist in this project and is not declared "
                f"on the {SHEET_PHASES} sheet of this workbook.",
            )
            continue
        # The same refusal `stage_create_building` makes, made early enough for
        # the operator to see it beside the row rather than as a failed apply.
        # A spreadsheet is not a way past a retired phase.
        if parent is not None and not parent.is_active:
            batch.error(row, "phase_code", f"Phase '{phase_code}' is not active.")
            continue
        fields: dict[str, Any] = {"code": code, "name": values["building_name"]}
        for column in ("zone", "block", "entrance_wing"):
            if values[column]:
                fields[column] = values[column]
        sequence = _int(batch, row=row, column="sequence", raw=values["sequence"])
        if sequence is not None:
            fields["sequence"] = sequence
        if not _through_the_request_contract(
            batch,
            row=row,
            model=BuildingCreateRequest,
            payload={**fields, "phase_id": _UNRESOLVED_PARENT},
            columns=_BUILDING_FIELD_COLUMNS,
        ):
            continue
        action = _action_for(
            batch,
            row=row,
            column="building_code",
            mode=mode,
            existing=existing.get((phase_code, code)),
            what=f"Building '{code}' in phase '{phase_code}'",
        )
        if action is None:
            continue
        structure.buildings.append(
            Declared(
                SHEET_BUILDINGS,
                row,
                (phase_code, code),
                fields,
                action,
                existing.get((phase_code, code)),
            )
        )


def _read_floors(
    structure: Structure,
    *,
    rows: list[tuple[int, dict[str, str]]],
    mode: str,
    buildings: dict[tuple[str, str], Building],
    existing: dict[tuple[str, str, str], Floor],
) -> None:
    batch = structure.batch
    declared_buildings = {record.codes for record in structure.buildings}
    seen: dict[tuple[str, ...], int] = {}
    for row, values in rows:
        if not _required(batch, row=row, values=values, columns=FLOOR_COLUMNS):
            continue
        phase_code = _domain_value(
            batch,
            row=row,
            column="phase_code",
            call=lambda raw=values["phase_code"]: service.normalize_code(raw, label="A phase code"),
        )
        building_code = _domain_value(
            batch,
            row=row,
            column="building_code",
            call=lambda raw=values["building_code"]: service.normalize_code(
                raw, label="A building code"
            ),
        )
        code = _domain_value(
            batch,
            row=row,
            column="floor_code",
            call=lambda raw=values["floor_code"]: service.normalize_code(
                raw, label="A floor code", pattern=service.FLOOR_CODE_PATTERN
            ),
        )
        if phase_code is None or building_code is None or code is None:
            continue
        key = (phase_code, building_code, code)
        if _duplicate(
            batch,
            row=row,
            column="floor_code",
            key=key,
            seen=seen,
            what=f"Floor '{code}' in {phase_code}/{building_code}",
        ):
            continue
        parent = buildings.get((phase_code, building_code))
        if parent is None and (phase_code, building_code) not in declared_buildings:
            batch.error(
                row,
                "building_code",
                f"Building '{building_code}' does not exist under phase '{phase_code}' and "
                f"is not declared on the {SHEET_BUILDINGS} sheet of this workbook.",
            )
            continue
        if parent is not None and not parent.is_active:
            batch.error(row, "building_code", f"Building '{building_code}' is not active.")
            continue
        fields: dict[str, Any] = {"code": code, "label": values["floor_label"]}
        level = _int(batch, row=row, column="level_number", raw=values["level_number"])
        if level is not None:
            fields["level_number"] = level
        sequence = _int(batch, row=row, column="sequence", raw=values["sequence"])
        if sequence is not None:
            fields["sequence"] = sequence
        if not _through_the_request_contract(
            batch,
            row=row,
            model=FloorCreateRequest,
            payload={**fields, "building_id": _UNRESOLVED_PARENT},
            columns=_FLOOR_FIELD_COLUMNS,
        ):
            continue
        action = _action_for(
            batch,
            row=row,
            column="floor_code",
            mode=mode,
            existing=existing.get(key),
            what=f"Floor '{code}' in {phase_code}/{building_code}",
        )
        if action is None:
            continue
        structure.floors.append(Declared(SHEET_FLOORS, row, key, fields, action, existing.get(key)))


def _check_unit_parents(structure: Structure, *, floors: dict[tuple[str, str, str], Floor]) -> None:
    """Every unit must land on a floor that exists or that this workbook creates.

    ``parse_rows`` is asked to tolerate missing hierarchy, because most of a new
    development's hierarchy arrives on the three sheets above rather than in the
    database. That tolerance has to be paid for here: without this check a unit
    naming a floor nobody declared would quietly bring a nameless floor into
    existence, which is how a typo becomes a permanent record.
    """
    declared = {record.codes for record in structure.floors}
    batch = structure.batch
    batch.sheet = SHEET_UNITS
    for row in structure.batch.rows:
        key = row.hierarchy
        if key is None:
            continue
        codes = (key.phase_code.upper(), key.building_code.upper(), key.floor_code.upper())
        if codes in floors or codes in declared:
            continue
        batch.error(
            row.index,
            "floor_code",
            f"Floor '{key.floor_code}' does not exist under building "
            f"'{key.building_code}' in phase '{key.phase_code}', and is not declared on "
            f"the {SHEET_FLOORS} sheet of this workbook.",
        )


def parse(
    session: Session, *, project: Project, actor: ActorContext, body: bytes, mode: str
) -> Structure:
    """Read the whole workbook and check it, writing nothing.

    Every sheet is read even when an earlier one is wrong: an operator fixing a
    four-sheet workbook one sheet per upload would rather have the list.
    """
    if mode not in IMPORT_MODES:
        raise ValidationError("Import mode must be 'create' or 'upsert'.")

    book = _load(body)
    try:
        missing = [name for name in REQUIRED_SHEETS if name not in book.sheetnames]
        if missing:
            raise _refuse(
                f"That workbook is missing the {', '.join(missing)} sheet"
                f"{'s' if len(missing) > 1 else ''}. Download the template and fill that in."
            )
        version_cell = book[SHEET_INSTRUCTIONS][VERSION_CELL]
        if _is_formula(version_cell):
            raise _refuse("The template version cell contains a formula.")
        version = _text(version_cell.value)
        if version not in SUPPORTED_VERSIONS:
            raise _refuse(
                f"That workbook says its template version is '{version or 'blank'}', which "
                f"this system does not read. The current template is {TEMPLATE_VERSION} — "
                "download it again and move your rows across."
            )

        sheets = {
            name: _read_sheet(
                book,
                name=name,
                columns=columns,
                limit=MAX_UNIT_ROWS if name == SHEET_UNITS else MAX_STRUCTURE_ROWS,
            )
            for name, columns in SHEET_COLUMNS.items()
        }
    finally:
        book.close()

    structure = Structure(batch=import_service.Batch(), version=version)
    structure.rows_read = {name: len(rows) for name, rows in sheets.items()}

    # The same permission the manual form demands, demanded before a single row
    # is judged. A workbook is another way to ask, never a way to ask for more.
    if sheets[SHEET_PHASES]:
        require_project_configurer(actor)
    if any(sheets[name] for name in (SHEET_BUILDINGS, SHEET_FLOORS, SHEET_UNITS)):
        require_inventory_structure_writer(actor)

    phases, buildings, floors = _existing_hierarchy(session, project=project, actor=actor)

    structure.batch.sheet = SHEET_PHASES
    _read_phases(structure, rows=sheets[SHEET_PHASES], mode=mode, existing=phases)
    structure.batch.sheet = SHEET_BUILDINGS
    _read_buildings(
        structure, rows=sheets[SHEET_BUILDINGS], mode=mode, phases=phases, existing=buildings
    )
    structure.batch.sheet = SHEET_FLOORS
    _read_floors(
        structure, rows=sheets[SHEET_FLOORS], mode=mode, buildings=buildings, existing=floors
    )

    structure.batch.sheet = SHEET_UNITS
    import_service.parse_rows(
        session,
        project=project,
        actor=actor,
        headers=[column for column, _ in UNIT_COLUMNS],
        rows=sheets[SHEET_UNITS],
        mode=mode,
        # The hierarchy this workbook declares does not exist yet, so the unit
        # reader must not refuse a floor it is about to create. What it may not
        # do is invent one, which _check_unit_parents refuses immediately below.
        create_missing_hierarchy=True,
        batch=structure.batch,
    )
    _check_unit_parents(structure, floors=floors)
    structure.batch.sheet = None
    return structure


def report(structure: Structure, *, mode: str, applied: bool) -> dict[str, Any]:
    """What the workbook would do, or did, counted by object.

    The CSV report counts rows of one table, so it can key an error by its row
    number. A workbook has four sheets and four row 7s, so validity is counted
    over ``(sheet, row)`` pairs here rather than reusing that arithmetic with a
    collision in it.
    """
    batch = structure.batch
    bad = {(issue.sheet, issue.row) for issue in batch.issues if issue.severity == "error"}
    total_rows = sum(structure.rows_read.values())
    invalid = len(bad)
    counts = {
        "phases": structure.counts(structure.phases),
        "buildings": structure.counts(structure.buildings),
        "floors": structure.counts(structure.floors),
        "units": {"create": batch.create_count, "update": batch.update_count},
    }
    create_count = sum(entry["create"] for entry in counts.values())
    update_count = sum(entry["update"] for entry in counts.values())
    return {
        "mode": mode,
        "applied": applied,
        "template_version": structure.version,
        "total_rows": total_rows,
        "create_count": create_count,
        "update_count": update_count,
        "valid_rows": max(total_rows - invalid, 0),
        "invalid_rows": invalid,
        "error_count": batch.error_count,
        "warning_count": batch.warning_count,
        "structure": {
            "rows_read": structure.rows_read,
            "records": counts,
        },
        "issues": [
            {
                "sheet": issue.sheet,
                "row": issue.row,
                "column": issue.column,
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in batch.issues[: import_service.MAX_ISSUES]
        ],
        "issues_truncated": len(batch.issues) > import_service.MAX_ISSUES,
    }


def validate(
    session: Session, *, project: Project, actor: ActorContext, body: bytes, mode: str
) -> dict[str, Any]:
    """Check a workbook and write nothing."""
    structure = parse(session, project=project, actor=actor, body=body, mode=mode)
    session.rollback()
    return report(structure, mode=mode, applied=False)


def apply(
    session: Session, *, project: Project, actor: ActorContext, body: bytes, mode: str
) -> dict[str, Any]:
    """Write the whole workbook or none of it.

    The bytes are read again from scratch: a caller cannot hand back a summary
    from an earlier validate and have it believed, and the file on the
    operator's disk may not be the file they validated.

    One transaction covers all four sheets. A unit that fails on the last row
    takes every phase, building and floor of the same workbook down with it,
    because a half-loaded development is worse than a refused one — nobody can
    tell which half is real.
    """
    project = lock_project(session, project.id)
    structure = parse(session, project=project, actor=actor, body=body, mode=mode)
    if structure.batch.error_count:
        session.rollback()
        return report(structure, mode=mode, applied=False)

    try:
        _write_hierarchy(session, project=project, actor=actor, structure=structure)
        import_service.apply_rows(session, project=project, actor=actor, batch=structure.batch)
        record_event(
            session,
            action="inventory.import_applied",
            entity_type=ENTITY_IMPORT,
            entity_id=project.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            after={
                "mode": mode,
                "format": "workbook",
                "template_version": structure.version,
                "rows": sum(structure.rows_read.values()),
                "phases": len(structure.phases),
                "buildings": len(structure.buildings),
                "floors": len(structure.floors),
                "units": len(structure.batch.rows),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return report(structure, mode=mode, applied=True)


def _write_hierarchy(
    session: Session, *, project: Project, actor: ActorContext, structure: Structure
) -> None:
    """Create or update the declared hierarchy through the domain's own rules.

    Every call here is an ``inventory.service`` mutation primitive — the same
    code the manual form runs. This module contributes the workbook: which rows
    were asked for, in which order, and that they all land together. It
    contributes no rule about what a phase, building or floor may be, and no
    audit content of its own.

    The primitives do not commit, which is the whole reason they exist. An
    earlier version of this function built the ORM rows itself to get one
    transaction, and in doing so quietly became a second implementation: it
    accepted codes the API refused, skipped the active-parent checks, and wrote
    an audit event carrying a code and a name where the real one carries the
    whole before and after. The transaction boundary belongs to the batch; the
    rules belong to the service; those are two different problems and they now
    have two different answers.
    """
    phases = {
        phase.code: phase for phase in service.list_phases(session, project=project, actor=actor)
    }
    for record in structure.phases:
        code = record.codes[0]
        if record.action == "create":
            phases[code] = service.stage_create_phase(
                session,
                project=project,
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                **record.fields,
            )
        else:
            # A code is identity and is never an update. Everything else the
            # sheet states is what the record should now say, and the primitive
            # writes the real before/after snapshot for it.
            phases[code] = service.stage_update_phase(
                session,
                phase=record.existing,
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                **{key: value for key, value in record.fields.items() if key != "code"},
            )

    buildings: dict[tuple[str, str], Building] = {}
    for building in service.list_buildings(session, project=project, actor=actor):
        for code, phase in phases.items():
            if phase.id == building.phase_id:
                buildings[(code, building.code)] = building
    for record in structure.buildings:
        phase_code, _building_code = record.codes
        if record.action == "create":
            buildings[record.codes] = service.stage_create_building(
                session,
                project=project,
                phase=phases[phase_code],
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                **record.fields,
            )
        else:
            buildings[record.codes] = service.stage_update_building(
                session,
                building=record.existing,
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                **{key: value for key, value in record.fields.items() if key != "code"},
            )

    for record in structure.floors:
        phase_code, building_code, _floor_code = record.codes
        if record.action == "create":
            service.stage_create_floor(
                session,
                project=project,
                building=buildings[(phase_code, building_code)],
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                **record.fields,
            )
        else:
            service.stage_update_floor(
                session,
                floor=record.existing,
                actor_user_id=actor.user_id,
                correlation_id=actor.correlation_id,
                **{key: value for key, value in record.fields.items() if key != "code"},
            )
