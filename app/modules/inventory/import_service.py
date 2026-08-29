"""Bulk inventory load from CSV.

The reference development is 247 units. Requiring an operator to create every
phase, building, floor and unit by hand would push the real work back into a
spreadsheet, which is the thing this system exists to replace.

It is the standard library's ``csv`` and nothing else. No pandas, no openpyxl,
no upload framework: the browser reads the file with ``File.text()`` and posts
the characters, so there is no multipart parser and no new dependency carried
for one screen.

Two endpoints, and the split matters. **Validate** writes nothing and reports
what would happen. **Apply** parses the file again from scratch and commits the
whole batch or none of it — it never trusts a validation response, because the
file may have changed and a caller can send any summary it likes.

CSV content is data. Nothing here evaluates a cell: a value beginning with ``=``
is text that happens to start with an equals sign.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.inventory import service
from app.modules.inventory.custom_fields import definitions_for, write_values
from app.modules.inventory.models import (
    AREA_SCHEDULE_APPROVED,
    AREA_SCHEDULE_DRAFT,
    ASSET_CLASSES,
    COMMERCIAL_STATUS_UNRELEASED,
    ENTITY_IMPORT,
    ENTITY_UNIT,
    AreaType,
    Building,
    Floor,
    Phase,
    Unit,
    UnitAreaSchedule,
    UnitAreaValue,
)
from app.modules.inventory.permissions import visible_phase_ids
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project
from app.modules.settings.service import require_active_reference_value

#: Generous for a development: the reference project is 247 units. The point is
#: to refuse a file nobody meant to send, not to ration ordinary work.
MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024

#: The most issues returned in one response. The counts stay complete; only the
#: detail list is capped, because a 5,000-row mistake should not answer with a
#: 5,000-entry body nobody can read.
MAX_ISSUES = 200

#: Row 1 of a CSV is the header. Its problems belong to the file, not a record.
HEADER_ROW = 1

#: Written into a cell to mean "clear this value". An empty cell means "leave it
#: alone", and the two are different requests: without an explicit token an
#: update could never clear anything, and a blank column would wipe every row.
CLEAR_TOKEN = "<CLEAR>"

IMPORT_MODES = ("create", "upsert")

_HIERARCHY_COLUMNS = (
    "phase_code",
    "phase_name",
    "building_code",
    "building_name",
    "floor_code",
    "floor_label",
)

_UNIT_TEXT_COLUMNS = (
    "unit_number",
    "unit_reference",
    "asset_class",
    "unit_type_code",
    "furnishing_specification_code",
    "floor_band_code",
    "orientation_code",
    "view_class_code",
    "accessibility_code",
    "garden_class_code",
    "release_batch",
    "block_reason",
)
_UNIT_INT_COLUMNS = ("sequence", "bedrooms", "bathrooms")
_UNIT_BOOL_COLUMNS = (
    "has_maid_room",
    "is_duplex",
    "is_penthouse",
    "is_corner",
    "pool_access",
    "drawings_approved",
    "legal_sale_eligible",
)
_UNIT_DECIMAL_COLUMNS = ("plot_coverage_fraction",)
_UNIT_DATE_COLUMNS = ("release_date",)
_AREA_COLUMNS = ("area_revision", "area_source", "area_measured_date", "area_reconciled")

#: The reference-value category behind each configurable unit column.
_CODE_CATEGORIES = {
    "unit_type_code": "unit_type",
    "furnishing_specification_code": "furnishing_specification",
    "floor_band_code": "floor_band",
    "orientation_code": "orientation",
    "view_class_code": "view_class",
    "accessibility_code": "accessibility",
    "garden_class_code": "garden_class",
}

#: Every column the importer understands, beside the ``area:`` and ``custom:``
#: prefixed ones. Pricing columns are absent: there is no price to import yet.
KNOWN_COLUMNS = frozenset(
    (
        "action",
        "unit_id",
        *_HIERARCHY_COLUMNS,
        *_UNIT_TEXT_COLUMNS,
        *_UNIT_INT_COLUMNS,
        *_UNIT_BOOL_COLUMNS,
        *_UNIT_DECIMAL_COLUMNS,
        *_UNIT_DATE_COLUMNS,
        *_AREA_COLUMNS,
    )
)

#: The header of the template offered in the interface.
TEMPLATE_COLUMNS = (
    "action",
    "unit_id",
    "phase_code",
    "phase_name",
    "building_code",
    "building_name",
    "floor_code",
    "floor_label",
    "unit_number",
    "unit_reference",
    "sequence",
    "asset_class",
    "unit_type_code",
    "bedrooms",
    "bathrooms",
    "has_maid_room",
    "is_duplex",
    "is_penthouse",
    "furnishing_specification_code",
    "floor_band_code",
    "orientation_code",
    "view_class_code",
    "is_corner",
    "pool_access",
    "accessibility_code",
    "garden_class_code",
    "plot_coverage_fraction",
    "drawings_approved",
    "legal_sale_eligible",
    "release_date",
    "release_batch",
    "block_reason",
    "area_revision",
    "area_source",
    "area_measured_date",
    "area_reconciled",
)

_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


@dataclass(slots=True)
class Issue:
    row: int
    column: str | None
    severity: str
    message: str


@dataclass(slots=True)
class HierarchyKey:
    """Where a row's unit belongs, by code rather than by identifier.

    Rows are read before anything is written, so a row that needs a phase two
    rows above it created has nothing to point at yet. Codes are what the file
    speaks in, so codes are what the parse carries.
    """

    phase_code: str
    building_code: str
    floor_code: str
    phase_name: str | None = None
    building_name: str | None = None
    floor_label: str | None = None


@dataclass(slots=True)
class Row:
    index: int
    action: str
    unit_id: uuid.UUID | None
    hierarchy: HierarchyKey | None
    fields: dict[str, Any]
    cleared: set[str]
    areas: dict[str, Decimal]
    customs: dict[str, Any]
    area_revision: str
    area_source: str
    area_measured_date: str
    area_reconciled: bool


@dataclass(slots=True)
class Batch:
    """What one parse produced: the rows to act on, and everything wrong."""

    issues: list[Issue] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    create_count: int = 0
    update_count: int = 0
    total_rows: int = 0

    def error(self, row: int, column: str | None, message: str) -> None:
        self.issues.append(Issue(row, column, "error", message))

    def warn(self, row: int, column: str | None, message: str) -> None:
        self.issues.append(Issue(row, column, "warning", message))

    @property
    def error_rows(self) -> set[int]:
        return {issue.row for issue in self.issues if issue.severity == "error"}

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")


def _decode(body: bytes) -> str:
    if len(body) > MAX_BYTES:
        raise ValidationError(
            f"That file is larger than the {MAX_BYTES // (1024 * 1024)} MB limit."
        )
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("The file must be UTF-8 encoded CSV.") from exc
    if not text.strip():
        raise ValidationError("That file is empty.")
    return text


def _parse_bool(raw: str) -> bool | None:
    lowered = raw.strip().casefold()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    return None


def _cell(row: dict[str, str], column: str) -> str:
    return (row.get(column) or "").strip()


def template_csv() -> str:
    """A header row and one worked example, so the file shape is not guesswork."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([*TEMPLATE_COLUMNS, "area:INTERNAL", "area:BALCONY"])
    writer.writerow(
        [
            "create",
            "",
            "PHASE-1",
            "Phase 1",
            "B1",
            "Building 1",
            "01",
            "First floor",
            "101",
            "B1-101",
            "1",
            "apartment",
            "",
            "2",
            "2",
            "false",
            "false",
            "false",
            *[""] * 9,
            "false",
            "false",
            "",
            "",
            "",
            "R0",
            "Architect drawings",
            "",
            "true",
            "104.5000",
            "12.0000",
        ]
    )
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def parse(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    body: bytes,
    mode: str,
    create_missing_hierarchy: bool,
) -> Batch:
    """Read and check the whole file without writing anything.

    Every row is checked even after the first failure: an operator fixing a
    247-row file one error per attempt would rather have the list.
    """
    if mode not in IMPORT_MODES:
        raise ValidationError("Import mode must be 'create' or 'upsert'.")
    reader = csv.DictReader(io.StringIO(_decode(body)))
    if reader.fieldnames is None:
        raise ValidationError("That file has no header row.")

    batch = Batch()
    area_types = {
        area_type.code: area_type
        for area_type in service.list_area_types(
            session, project_id=project.id, include_inactive=False
        )
    }
    definitions = {
        definition.field_key
        for definition in definitions_for(session, entity_type="unit", project=project)
    }
    area_columns, custom_columns = _read_header(
        batch, headers=reader.fieldnames, area_types=area_types, definitions=definitions
    )

    allowed = visible_phase_ids(session, project_id=project.id, actor=actor)
    visible = set(session.scalars(allowed)) if allowed is not None else None
    existing = _Existing(session, project=project)
    references_seen: dict[str, int] = {}
    numbers_seen: dict[tuple[str, str, str], int] = {}

    for index, raw in enumerate(reader, start=2):
        if batch.total_rows >= MAX_ROWS:
            batch.error(index, None, f"This import accepts at most {MAX_ROWS} rows.")
            break
        batch.total_rows += 1
        row = _read_row(
            session,
            batch=batch,
            index=index,
            raw=raw,
            project=project,
            mode=mode,
            create_missing_hierarchy=create_missing_hierarchy,
            existing=existing,
            visible=visible,
            area_columns=area_columns,
            custom_columns=custom_columns,
            references_seen=references_seen,
            numbers_seen=numbers_seen,
        )
        if row is None:
            continue
        batch.rows.append(row)
        if row.action == "create":
            batch.create_count += 1
        else:
            batch.update_count += 1
    return batch


def _read_header(
    batch: Batch,
    *,
    headers: list[str],
    area_types: dict[str, AreaType],
    definitions: set[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Split the header into area columns, custom columns and the known rest.

    An unrecognised core column is an error, not a warning: it is almost always
    a typo in a column the operator believed was being read, and a silent skip
    would lose the data without saying so.
    """
    area_columns: dict[str, str] = {}
    custom_columns: dict[str, str] = {}
    for name in headers:
        header = (name or "").strip()
        if not header:
            continue
        if header.startswith("area:"):
            code = header[len("area:") :].strip().upper()
            if code not in area_types:
                batch.error(
                    HEADER_ROW, header, f"'{code}' is not an active area type of this project."
                )
            else:
                area_columns[header] = code
        elif header.startswith("custom:"):
            key = header[len("custom:") :].strip().lower()
            if key not in definitions:
                batch.error(
                    HEADER_ROW, header, f"'{key}' is not a field of a unit in this project."
                )
            else:
                custom_columns[header] = key
        elif header not in KNOWN_COLUMNS:
            batch.error(HEADER_ROW, header, f"'{header}' is not a column this import understands.")
    return area_columns, custom_columns


class _Existing:
    """The project's current hierarchy and units, read once for the whole file."""

    def __init__(self, session: Session, *, project: Project) -> None:
        self.phases = {
            phase.code: phase
            for phase in session.scalars(select(Phase).where(Phase.project_id == project.id))
        }
        self.buildings = {
            (building.phase_id, building.code): building
            for building in session.scalars(
                select(Building).where(Building.project_id == project.id)
            )
        }
        self.floors = {
            (floor.building_id, floor.code): floor
            for floor in session.scalars(select(Floor).where(Floor.project_id == project.id))
        }

    def floor_for(self, key: HierarchyKey) -> Floor | None:
        phase = self.phases.get(key.phase_code)
        if phase is None:
            return None
        building = self.buildings.get((phase.id, key.building_code))
        if building is None:
            return None
        return self.floors.get((building.id, key.floor_code))

    def phase_for(self, key: HierarchyKey) -> Phase | None:
        return self.phases.get(key.phase_code)


def _read_row(
    session: Session,
    *,
    batch: Batch,
    index: int,
    raw: dict[str, str],
    project: Project,
    mode: str,
    create_missing_hierarchy: bool,
    existing: _Existing,
    visible: set[uuid.UUID] | None,
    area_columns: dict[str, str],
    custom_columns: dict[str, str],
    references_seen: dict[str, int],
    numbers_seen: dict[tuple[str, str, str], int],
) -> Row | None:
    action = (_cell(raw, "action") or "").lower()
    unit_id_text = _cell(raw, "unit_id")
    unit: Unit | None = None

    if unit_id_text:
        try:
            unit_id = uuid.UUID(unit_id_text)
        except ValueError:
            batch.error(index, "unit_id", "That is not a valid unit identifier.")
            return None
        unit = session.scalars(
            select(Unit).where(Unit.id == unit_id, Unit.project_id == project.id)
        ).first()
        if unit is None:
            batch.error(index, "unit_id", "No unit with that identifier exists in this project.")
            return None
        action = action or "update"
    elif action == "update":
        # The reference is editable, so matching on it would update whichever row
        # currently carries the text. Identity is the UUID and nothing else.
        batch.error(
            index,
            "unit_id",
            "An update needs unit_id. A unit reference can be edited and is not identity.",
        )
        return None
    else:
        action = action or "create"

    if action not in {"create", "update"}:
        batch.error(index, "action", "Action must be 'create' or 'update'.")
        return None
    if mode == "create" and action == "update":
        batch.error(index, "action", "This import is in create mode and cannot update a unit.")
        return None

    hierarchy = _read_hierarchy(batch, index=index, raw=raw)
    if hierarchy is None and unit is None:
        return None

    floor = existing.floor_for(hierarchy) if hierarchy is not None else None
    if hierarchy is not None:
        if floor is None and not create_missing_hierarchy:
            batch.error(
                index,
                "floor_code",
                f"Floor '{hierarchy.floor_code}' does not exist in "
                f"{hierarchy.phase_code}/{hierarchy.building_code}.",
            )
        _check_no_rename(batch, index=index, key=hierarchy, existing=existing)

    phase = existing.phase_for(hierarchy) if hierarchy is not None else None
    if visible is not None:
        if phase is not None and phase.id not in visible:
            batch.error(index, "phase_code", "That phase is not available to you.")
            return None
        if phase is None and hierarchy is not None:
            batch.error(index, "phase_code", "You may not create a phase in this project.")
            return None
        if unit is not None and hierarchy is None:
            unit_floor = session.get(Floor, unit.floor_id)
            building = session.get(Building, unit_floor.building_id) if unit_floor else None
            if building is None or building.phase_id not in visible:
                batch.error(index, "unit_id", "That unit is not available to you.")
                return None

    fields, cleared = _read_unit_columns(batch, index=index, raw=raw)
    _check_required(batch, index=index, action=action, fields=fields)
    _check_codes(session, batch, index=index, project=project, fields=fields)
    _check_reference(
        session,
        batch,
        index=index,
        project=project,
        fields=fields,
        unit=unit,
        references_seen=references_seen,
    )
    _check_number(batch, index=index, fields=fields, hierarchy=hierarchy, numbers_seen=numbers_seen)

    areas = _read_areas(batch, index=index, raw=raw, area_columns=area_columns)
    customs = {
        key: (None if _cell(raw, column) == CLEAR_TOKEN else _cell(raw, column))
        for column, key in custom_columns.items()
        if _cell(raw, column)
    }
    if areas and not _cell(raw, "area_revision"):
        batch.error(index, "area_revision", "Imported areas need a revision code.")

    return Row(
        index=index,
        action=action,
        unit_id=unit.id if unit is not None else None,
        hierarchy=hierarchy,
        fields=fields,
        cleared=cleared,
        areas=areas,
        customs=customs,
        area_revision=_cell(raw, "area_revision"),
        area_source=_cell(raw, "area_source"),
        area_measured_date=_cell(raw, "area_measured_date"),
        area_reconciled=bool(_parse_bool(_cell(raw, "area_reconciled"))),
    )


def _read_hierarchy(batch: Batch, *, index: int, raw: dict[str, str]) -> HierarchyKey | None:
    codes = {
        "phase_code": _cell(raw, "phase_code").upper(),
        "building_code": _cell(raw, "building_code").upper(),
        "floor_code": _cell(raw, "floor_code").upper(),
    }
    if not any(codes.values()):
        return None
    missing = [column for column, value in codes.items() if not value]
    if missing:
        batch.error(
            index,
            missing[0],
            "phase_code, building_code and floor_code are all needed to place a unit.",
        )
        return None
    return HierarchyKey(
        phase_code=codes["phase_code"],
        building_code=codes["building_code"],
        floor_code=codes["floor_code"],
        phase_name=_cell(raw, "phase_name") or None,
        building_name=_cell(raw, "building_name") or None,
        floor_label=_cell(raw, "floor_label") or None,
    )


def _check_no_rename(batch: Batch, *, index: int, key: HierarchyKey, existing: _Existing) -> None:
    """A unit import never renames the hierarchy it is loaded into."""
    phase = existing.phases.get(key.phase_code)
    if phase is not None and key.phase_name and phase.name != key.phase_name:
        batch.error(
            index,
            "phase_name",
            f"Phase '{key.phase_code}' is named '{phase.name}'. An import does not rename it.",
        )
    if phase is None:
        return
    building = existing.buildings.get((phase.id, key.building_code))
    if building is not None and key.building_name and building.name != key.building_name:
        batch.error(
            index,
            "building_name",
            f"Building '{key.building_code}' is named '{building.name}'. "
            "An import does not rename it.",
        )
    if building is None:
        return
    floor = existing.floors.get((building.id, key.floor_code))
    if floor is not None and key.floor_label and floor.label != key.floor_label:
        batch.error(
            index,
            "floor_label",
            f"Floor '{key.floor_code}' is labelled '{floor.label}'. An import does not rename it.",
        )


def _read_unit_columns(
    batch: Batch, *, index: int, raw: dict[str, str]
) -> tuple[dict[str, Any], set[str]]:
    fields: dict[str, Any] = {}
    cleared: set[str] = set()

    def take(column: str) -> str | None:
        value = _cell(raw, column)
        if not value:
            return None
        if value == CLEAR_TOKEN:
            cleared.add(column)
            return None
        return value

    for column in _UNIT_TEXT_COLUMNS:
        value = take(column)
        if value is not None:
            fields[column] = value
    for column in _UNIT_INT_COLUMNS:
        value = take(column)
        if value is None:
            continue
        try:
            fields[column] = int(value)
        except ValueError:
            batch.error(index, column, f"'{value}' is not a whole number.")
    for column in _UNIT_BOOL_COLUMNS:
        value = _cell(raw, column)
        if not value:
            continue
        parsed = _parse_bool(value)
        if parsed is None:
            batch.error(index, column, f"'{value}' is not true or false.")
        else:
            fields[column] = parsed
    for column in _UNIT_DECIMAL_COLUMNS:
        value = take(column)
        if value is None:
            continue
        try:
            fields[column] = Decimal(value)
        except InvalidOperation:
            batch.error(index, column, f"'{value}' is not a number.")
    for column in _UNIT_DATE_COLUMNS:
        value = take(column)
        if value is None:
            continue
        try:
            fields[column] = date.fromisoformat(value)
        except ValueError:
            batch.error(index, column, f"'{value}' is not a date as YYYY-MM-DD.")
    return fields, cleared


def _check_required(batch: Batch, *, index: int, action: str, fields: dict[str, Any]) -> None:
    asset_class = fields.get("asset_class")
    if asset_class is not None and asset_class not in ASSET_CLASSES:
        batch.error(
            index, "asset_class", f"'{asset_class}' is not one of {', '.join(ASSET_CLASSES)}."
        )
    if action != "create":
        return
    for column in ("unit_number", "unit_reference", "asset_class"):
        if not fields.get(column):
            batch.error(index, column, "This column is required to create a unit.")


def _check_codes(
    session: Session, batch: Batch, *, index: int, project: Project, fields: dict[str, Any]
) -> None:
    for column, category in _CODE_CATEGORIES.items():
        code = fields.get(column)
        if code is None:
            continue
        try:
            require_active_reference_value(
                session,
                category=category,
                code=str(code),
                country_pack_id=project.country_pack_id,
            )
        except ValidationError as exc:
            batch.error(index, column, str(exc))


def _check_reference(
    session: Session,
    batch: Batch,
    *,
    index: int,
    project: Project,
    fields: dict[str, Any],
    unit: Unit | None,
    references_seen: dict[str, int],
) -> None:
    reference = fields.get("unit_reference")
    if not reference:
        return
    normalized = " ".join(str(reference).split())
    key = normalized.casefold()
    first = references_seen.get(key)
    if first is not None:
        batch.error(
            index, "unit_reference", f"Duplicate unit reference '{normalized}' (also row {first})."
        )
        return
    references_seen[key] = index
    clash = session.scalars(
        select(Unit).where(Unit.project_id == project.id, Unit.unit_reference == normalized)
    ).first()
    if clash is not None and (unit is None or clash.id != unit.id):
        batch.error(index, "unit_reference", f"Unit reference '{normalized}' already exists.")


def _check_number(
    batch: Batch,
    *,
    index: int,
    fields: dict[str, Any],
    hierarchy: HierarchyKey | None,
    numbers_seen: dict[tuple[str, str, str], int],
) -> None:
    number = fields.get("unit_number")
    if not number or hierarchy is None:
        return
    key = (hierarchy.phase_code, hierarchy.building_code + hierarchy.floor_code, str(number))
    first = numbers_seen.get(key)
    if first is not None:
        batch.error(
            index, "unit_number", f"Duplicate unit number '{number}' on this floor (row {first})."
        )
    else:
        numbers_seen[key] = index


def _read_areas(
    batch: Batch, *, index: int, raw: dict[str, str], area_columns: dict[str, str]
) -> dict[str, Decimal]:
    areas: dict[str, Decimal] = {}
    for column, code in area_columns.items():
        value = _cell(raw, column)
        if not value:
            continue
        try:
            amount = Decimal(value)
        except InvalidOperation:
            batch.error(index, column, f"'{value}' is not a number.")
            continue
        if amount < 0:
            batch.error(index, column, "An area cannot be negative.")
            continue
        areas[code] = amount
    return areas


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def report(batch: Batch, *, mode: str, applied: bool) -> dict[str, Any]:
    # A header the import cannot read is not one row's problem: no data row was
    # ever checked against it, so none of them can be called valid. Counting
    # them as valid would put "12 valid rows" next to "a column we do not
    # understand", and an operator would reasonably read that as safe to apply.
    invalid = (
        batch.total_rows if HEADER_ROW in batch.error_rows else len(batch.error_rows - {HEADER_ROW})
    )
    return {
        "mode": mode,
        "applied": applied,
        "total_rows": batch.total_rows,
        "create_count": batch.create_count,
        "update_count": batch.update_count,
        "valid_rows": max(batch.total_rows - invalid, 0),
        "invalid_rows": invalid,
        "error_count": batch.error_count,
        "warning_count": batch.warning_count,
        "issues": [
            {
                "row": issue.row,
                "column": issue.column,
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in batch.issues[:MAX_ISSUES]
        ],
        "issues_truncated": len(batch.issues) > MAX_ISSUES,
    }


def validate(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    body: bytes,
    mode: str,
    create_missing_hierarchy: bool,
) -> dict[str, Any]:
    """Check a file and write nothing.

    The session is rolled back before returning, so a validation run cannot
    leave anything behind even if a check touched the identity map on its way.
    """
    batch = parse(
        session,
        project=project,
        actor=actor,
        body=body,
        mode=mode,
        create_missing_hierarchy=create_missing_hierarchy,
    )
    session.rollback()
    return report(batch, mode=mode, applied=False)


# --------------------------------------------------------------------------- #
# Applying
# --------------------------------------------------------------------------- #


def apply(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    body: bytes,
    mode: str,
    create_missing_hierarchy: bool,
    approve_area_schedules: bool = False,
) -> dict[str, Any]:
    """Parse the file again and commit the whole batch, or none of it.

    The project row is locked once at the start rather than per row: this is one
    structural change to one project's catalogue, and hundreds of sequential
    locks would be slower and no safer.

    Nothing in here calls a service function that commits. The batch owns its
    transaction boundary, so one bad row leaves no half-loaded catalogue behind.
    """
    project = lock_project(session, project.id)
    batch = parse(
        session,
        project=project,
        actor=actor,
        body=body,
        mode=mode,
        create_missing_hierarchy=create_missing_hierarchy,
    )
    if batch.error_count:
        session.rollback()
        return report(batch, mode=mode, applied=False)

    try:
        floors = _materialise_hierarchy(session, project=project, actor=actor, batch=batch)
        for row in batch.rows:
            _apply_row(
                session,
                project=project,
                actor=actor,
                row=row,
                floors=floors,
                approve=approve_area_schedules,
            )
        record_event(
            session,
            action="inventory.import_applied",
            entity_type=ENTITY_IMPORT,
            entity_id=project.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            after={
                "mode": mode,
                "rows": batch.total_rows,
                "created": batch.create_count,
                "updated": batch.update_count,
            },
        )
        session.commit()
    except Exception:
        # A half-loaded catalogue is worse than a refused file: nobody can tell
        # which half is real.
        session.rollback()
        raise
    return report(batch, mode=mode, applied=True)


def _materialise_hierarchy(
    session: Session, *, project: Project, actor: ActorContext, batch: Batch
) -> dict[tuple[str, str, str], Floor]:
    """Create every phase, building and floor the batch needs, top down."""
    existing = _Existing(session, project=project)
    resolved: dict[tuple[str, str, str], Floor] = {}
    for row in batch.rows:
        key = row.hierarchy
        if key is None:
            continue
        cache_key = (key.phase_code, key.building_code, key.floor_code)
        if cache_key in resolved:
            continue
        phase = existing.phases.get(key.phase_code)
        if phase is None:
            phase = Phase(
                project_id=project.id,
                code=key.phase_code,
                name=key.phase_name or key.phase_code,
                created_by_user_id=actor.user_id,
            )
            session.add(phase)
            session.flush()
            existing.phases[key.phase_code] = phase
            record_event(
                session,
                action="phase.created",
                entity_type="phase",
                entity_id=phase.id,
                correlation_id=actor.correlation_id,
                actor_user_id=actor.user_id,
                after={"code": phase.code, "name": phase.name, "source": "import"},
            )
        building = existing.buildings.get((phase.id, key.building_code))
        if building is None:
            building = Building(
                project_id=project.id,
                phase_id=phase.id,
                code=key.building_code,
                name=key.building_name or key.building_code,
                created_by_user_id=actor.user_id,
            )
            session.add(building)
            session.flush()
            existing.buildings[(phase.id, key.building_code)] = building
            record_event(
                session,
                action="building.created",
                entity_type="building",
                entity_id=building.id,
                correlation_id=actor.correlation_id,
                actor_user_id=actor.user_id,
                after={"code": building.code, "name": building.name, "source": "import"},
            )
        floor = existing.floors.get((building.id, key.floor_code))
        if floor is None:
            floor = Floor(
                project_id=project.id,
                building_id=building.id,
                code=key.floor_code,
                label=key.floor_label or key.floor_code,
                created_by_user_id=actor.user_id,
            )
            session.add(floor)
            session.flush()
            existing.floors[(building.id, key.floor_code)] = floor
            record_event(
                session,
                action="floor.created",
                entity_type="floor",
                entity_id=floor.id,
                correlation_id=actor.correlation_id,
                actor_user_id=actor.user_id,
                after={"code": floor.code, "label": floor.label, "source": "import"},
            )
        resolved[cache_key] = floor
    return resolved


def _apply_row(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    row: Row,
    floors: dict[tuple[str, str, str], Floor],
    approve: bool,
) -> None:
    fields = dict(row.fields)
    for column in row.cleared:
        fields[column] = None
    floor = (
        floors[(row.hierarchy.phase_code, row.hierarchy.building_code, row.hierarchy.floor_code)]
        if row.hierarchy is not None
        else None
    )

    if row.unit_id is None:
        unit = Unit(
            project_id=project.id,
            floor_id=floor.id,
            unit_number=str(fields.pop("unit_number")),
            unit_reference=" ".join(str(fields.pop("unit_reference")).split()),
            asset_class=str(fields.pop("asset_class")),
            created_by_user_id=actor.user_id,
        )
        session.add(unit)
        for name, value in fields.items():
            setattr(unit, name, value)
        session.flush()
        record_event(
            session,
            action="unit.created",
            entity_type=ENTITY_UNIT,
            entity_id=unit.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            after={"unit_reference": unit.unit_reference, "source": "import"},
        )
    else:
        unit = session.get(Unit, row.unit_id)
        before = {"unit_reference": unit.unit_reference, "floor_id": str(unit.floor_id)}
        if floor is not None and floor.id != unit.floor_id:
            if unit.commercial_status != COMMERCIAL_STATUS_UNRELEASED:
                raise ValidationError(
                    f"Row {row.index}: a unit can only be moved while it is unreleased."
                )
            unit.floor_id = floor.id
        for name, value in fields.items():
            if name == "unit_reference" and value is not None:
                value = " ".join(str(value).split())
            setattr(unit, name, value)
        session.flush()
        record_event(
            session,
            action="unit.updated",
            entity_type=ENTITY_UNIT,
            entity_id=unit.id,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            before=before,
            after={"unit_reference": unit.unit_reference, "source": "import"},
        )

    if row.customs:
        write_values(
            session,
            entity_type="unit",
            entity=unit,
            actor=actor,
            values=row.customs,
            change_reason="Bulk inventory import",
        )
    if row.areas:
        _apply_areas(session, project=project, actor=actor, unit=unit, row=row, approve=approve)


def _apply_areas(
    session: Session,
    *,
    project: Project,
    actor: ActorContext,
    unit: Unit,
    row: Row,
    approve: bool,
) -> None:
    """Record imported areas as a new revision, never as an overwrite.

    The measurement a unit was sold against stays exactly as it was. A corrected
    measurement is a new revision, and it becomes current only when somebody
    with the authority approves it — through the same checks the API applies.
    """
    area_types = {
        area_type.code: area_type
        for area_type in service.list_area_types(
            session, project_id=project.id, include_inactive=False
        )
    }
    revision = row.area_revision.upper()
    clash = session.scalars(
        select(UnitAreaSchedule).where(
            UnitAreaSchedule.unit_id == unit.id, UnitAreaSchedule.revision_code == revision
        )
    ).first()
    if clash is not None:
        raise ValidationError(
            f"Row {row.index}: revision '{revision}' already exists for this unit."
        )

    schedule = UnitAreaSchedule(
        project_id=project.id,
        unit_id=unit.id,
        revision_code=revision,
        status=AREA_SCHEDULE_DRAFT,
        source=row.area_source or "import",
        measured_date=(
            date.fromisoformat(row.area_measured_date) if row.area_measured_date else None
        ),
        reconciled=row.area_reconciled,
        created_by_user_id=actor.user_id,
    )
    session.add(schedule)
    session.flush()
    for code, amount in row.areas.items():
        session.add(
            UnitAreaValue(
                project_id=project.id,
                unit_area_schedule_id=schedule.id,
                area_type_id=area_types[code].id,
                raw_area=amount,
            )
        )
    session.flush()
    record_event(
        session,
        action="unit_area_schedule.created",
        entity_type="unit_area_schedule",
        entity_id=schedule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after={"revision_code": schedule.revision_code, "source": "import"},
    )
    if not approve:
        return

    if not schedule.reconciled:
        raise ValidationError(
            f"Row {row.index}: an area revision cannot be approved until it is reconciled."
        )
    missing = [
        area_type.code
        for area_type in area_types.values()
        if area_type.required_for_release and area_type.code not in row.areas
    ]
    if missing:
        raise ValidationError(
            f"Row {row.index}: missing required areas {', '.join(sorted(missing))}."
        )
    current = session.scalars(
        select(UnitAreaSchedule).where(
            UnitAreaSchedule.unit_id == unit.id,
            UnitAreaSchedule.status == AREA_SCHEDULE_APPROVED,
        )
    ).first()
    if current is not None:
        current.status = "superseded"
        session.flush()
    schedule.status = AREA_SCHEDULE_APPROVED
    schedule.approved_by_user_id = actor.user_id
    schedule.approved_at = func.now()
    session.flush()
    record_event(
        session,
        action="unit_area_schedule.approved",
        entity_type="unit_area_schedule",
        entity_id=schedule.id,
        correlation_id=actor.correlation_id,
        actor_user_id=actor.user_id,
        after={"revision_code": schedule.revision_code, "source": "import"},
    )
