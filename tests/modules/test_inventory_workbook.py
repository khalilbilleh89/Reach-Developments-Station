"""The operator's inventory workbook: four sheets, one transaction, no formulas.

The CSV importer this sits beside is more capable and is not going anywhere.
What it cannot do is let a phase exist before a unit mentions it, so a team
laying out a development has to invent units to describe a building. These
sheets can, which is the whole reason the workbook exists — and the reason most
of the tests below are about hierarchy that has no units under it yet.

Two properties carry the rest. **A workbook is data**: a cell containing
``=1+1`` is refused, never resolved, and the value Excel cached is never read.
**A workbook is one batch**: four sheets validate together and apply together,
so a unit failing on the last row takes that workbook's phases with it.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.inventory import workbook
from app.modules.inventory.models import Building, Floor, Phase, Unit
from tests.modules.conftest import inventory_url

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --------------------------------------------------------------------------- #
# Building workbooks to send
# --------------------------------------------------------------------------- #


def _book(
    *,
    phases: tuple[dict[str, object], ...] = (),
    buildings: tuple[dict[str, object], ...] = (),
    floors: tuple[dict[str, object], ...] = (),
    units: tuple[dict[str, object], ...] = (),
    version: str | None = None,
    edit: Callable[[Workbook], None] | None = None,
) -> bytes:
    """A filled-in copy of the real template.

    Built from ``workbook.template()`` rather than from a hand-made file, so
    every test here also proves the template the operator downloads is the file
    the parser accepts. A fixture assembled independently could drift from the
    template and none of these tests would notice.
    """
    book = load_workbook(io.BytesIO(workbook.template()))
    if version is not None:
        book[workbook.SHEET_INSTRUCTIONS][workbook.VERSION_CELL] = version
    for name, rows in (
        (workbook.SHEET_PHASES, phases),
        (workbook.SHEET_BUILDINGS, buildings),
        (workbook.SHEET_FLOORS, floors),
        (workbook.SHEET_UNITS, units),
    ):
        sheet = book[name]
        columns = [column for column, _ in workbook.SHEET_COLUMNS[name]]
        for offset, row in enumerate(rows, start=workbook.FIRST_DATA_ROW):
            for position, column in enumerate(columns, start=1):
                if column in row:
                    sheet.cell(row=offset, column=position, value=row[column])
    if edit is not None:
        edit(book)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


PHASE = {"phase_code": "PHASE-1", "phase_name": "Phase 1"}
BUILDING = {"phase_code": "PHASE-1", "building_code": "B1", "building_name": "Building 1"}
FLOOR = {
    "phase_code": "PHASE-1",
    "building_code": "B1",
    "floor_code": "01",
    "floor_label": "First floor",
}


def _unit(number: str, reference: str, **overrides: object) -> dict[str, object]:
    row = {
        "phase_code": "PHASE-1",
        "building_code": "B1",
        "floor_code": "01",
        "unit_number": number,
        "unit_reference": reference,
        "asset_class": "apartment",
    }
    row.update(overrides)
    return row


def _validate(client: TestClient, project_id: str, body: bytes, mode: str = "create") -> dict:
    response = client.post(
        f"{inventory_url(project_id)}/import/workbook/validate?mode={mode}",
        content=body,
        headers={"Content-Type": XLSX},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _apply(client: TestClient, project_id: str, body: bytes, mode: str = "create") -> dict:
    response = client.post(
        f"{inventory_url(project_id)}/import/workbook/apply?mode={mode}",
        content=body,
        headers={"Content-Type": XLSX},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _messages(report: dict) -> str:
    return " | ".join(
        f"{issue['sheet']}:{issue['row']}:{issue['column']}:{issue['message']}"
        for issue in report["issues"]
    )


# --------------------------------------------------------------------------- #
# The template itself
# --------------------------------------------------------------------------- #


class TestTheTemplateIsTheContract:
    """What an operator downloads is what the parser reads.

    Every assertion here is about the file rather than about a constant, because
    a template generated from the same tuple it is checked against proves only
    that the tuple exists.
    """

    def test_the_download_is_a_real_workbook_named_for_the_project(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        response = admin_client.get(f"{inventory_url(operational_project)}/import/template.xlsx")

        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(XLSX)
        assert "inventory-template.xlsx" in response.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert "xl/workbook.xml" in archive.namelist()

    def test_it_carries_every_sheet_the_parser_requires(self) -> None:
        book = load_workbook(io.BytesIO(workbook.template()))

        assert book.sheetnames == list(workbook.REQUIRED_SHEETS)

    def test_the_template_version_is_in_a_cell_not_the_filename(self) -> None:
        """A downloaded file is renamed, copied and mailed on. A cell is not."""
        book = load_workbook(io.BytesIO(workbook.template()))
        notes = book[workbook.SHEET_INSTRUCTIONS]

        assert notes[workbook.VERSION_LABEL_CELL].value == workbook.VERSION_LABEL
        assert notes[workbook.VERSION_CELL].value == workbook.TEMPLATE_VERSION
        assert workbook.TEMPLATE_VERSION in workbook.SUPPORTED_VERSIONS

    def test_every_sheet_has_exactly_the_headers_the_contract_names(self) -> None:
        book = load_workbook(io.BytesIO(workbook.template()))

        for name, columns in workbook.SHEET_COLUMNS.items():
            written = [cell.value for cell in book[name][workbook.HEADER_ROW]]
            assert written == [column for column, _ in columns], name

    def test_the_units_sheet_speaks_only_columns_the_importer_already_knows(self) -> None:
        """One vocabulary, not two.

        The Units sheet is a subset of the CSV importer's columns on purpose: a
        column here that the shared row reader had never heard of would be a
        second definition of what a unit is.
        """
        from app.modules.inventory import import_service

        for column, _ in workbook.UNIT_COLUMNS:
            assert column in import_service.KNOWN_COLUMNS, column

    def test_it_carries_no_formula_anywhere(self) -> None:
        """The template must not teach the shape the parser refuses."""
        book = load_workbook(io.BytesIO(workbook.template()))

        for name in book.sheetnames:
            for row in book[name].iter_rows():
                for cell in row:
                    assert not (isinstance(cell.value, str) and cell.value.startswith("=")), (
                        f"{name}!{cell.coordinate}"
                    )


# --------------------------------------------------------------------------- #
# Hierarchy that exists before any unit does
# --------------------------------------------------------------------------- #


class TestStructureCanExistBeforeUnits:
    """The reason this workbook exists at all.

    The CSV importer materialises a phase because some unit row named it, so a
    development cannot be laid out before its units are known. Every test here
    loads hierarchy with no unit under it.
    """

    def test_a_workbook_of_phases_alone_applies(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _apply(
            admin_client,
            operational_project,
            _book(phases=(PHASE, {"phase_code": "PHASE-2", "phase_name": "Phase 2"})),
        )

        assert report["applied"] is True, _messages(report)
        assert report["structure"]["records"]["phases"] == {"create": 2, "update": 0}
        assert report["structure"]["records"]["units"] == {"create": 0, "update": 0}
        codes = set(db.scalars(select(Phase.code)))
        assert {"PHASE-1", "PHASE-2"} <= codes

    def test_a_phase_and_a_building_with_no_units_applies(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _apply(
            admin_client, operational_project, _book(phases=(PHASE,), buildings=(BUILDING,))
        )

        assert report["applied"] is True, _messages(report)
        assert db.scalars(select(Building.code)).all() == ["B1"]

    def test_a_floor_with_no_units_applies(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _apply(
            admin_client,
            operational_project,
            _book(phases=(PHASE,), buildings=(BUILDING,), floors=(FLOOR,)),
        )

        assert report["applied"] is True, _messages(report)
        assert db.scalars(select(Floor.code)).all() == ["01"]
        assert db.scalars(select(Unit.id)).all() == []

    def test_the_whole_hierarchy_and_its_units_apply_as_one(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _apply(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(FLOOR,),
                units=(_unit("101", "B1-101"), _unit("102", "B1-102")),
            ),
        )

        assert report["applied"] is True, _messages(report)
        assert report["structure"]["records"]["units"] == {"create": 2, "update": 0}
        assert report["create_count"] == 5
        assert sorted(db.scalars(select(Unit.unit_reference))) == ["B1-101", "B1-102"]

    def test_a_phase_sheet_needs_the_permission_the_phase_form_needs(
        self, engineer_client: TestClient, operational_project: str
    ) -> None:
        """A workbook is another way to ask, never a way to ask for more.

        Creating a phase through the form requires a project configurer.
        Design and engineering may write structure but not phases, so the same
        person meets the same refusal here — before any row is read.
        """
        response = engineer_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(phases=(PHASE,)),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 403, response.text

    def test_the_same_person_may_still_load_buildings_and_floors(
        self, engineer_client: TestClient, admin_client: TestClient, operational_project: str
    ) -> None:
        """The refusal above is about phases, not about workbooks."""
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))

        report = _apply(
            engineer_client, operational_project, _book(buildings=(BUILDING,), floors=(FLOOR,))
        )

        assert report["applied"] is True, _messages(report)


# --------------------------------------------------------------------------- #
# Parents, duplicates and the messages an operator has to act on
# --------------------------------------------------------------------------- #


class TestTheReportNamesTheCellToFix:
    """A validation report is read by somebody holding the spreadsheet.

    "Foreign key violation" tells them nothing. Sheet, row, column and a
    sentence about the actual problem tells them where to click.
    """

    def test_a_building_under_an_undeclared_phase_names_the_sheet_and_the_phase(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(admin_client, operational_project, _book(buildings=(BUILDING,)))

        assert report["error_count"] == 1
        issue = report["issues"][0]
        assert issue["sheet"] == workbook.SHEET_BUILDINGS
        assert issue["row"] == 2
        assert issue["column"] == "phase_code"
        assert "PHASE-1" in issue["message"]
        assert workbook.SHEET_PHASES in issue["message"]

    def test_a_unit_on_an_undeclared_floor_is_refused_rather_than_inventing_one(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """The one thing tolerating missing hierarchy must not buy.

        The unit reader is told to accept hierarchy that does not exist yet,
        because most of it arrives on the sheets above. Without this check a
        typo in floor_code would quietly bring a nameless floor into being.
        """
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(FLOOR,),
                units=(_unit("101", "B1-101", floor_code="99"),),
            ),
        )

        assert report["error_count"] >= 1, _messages(report)
        assert any(
            issue["sheet"] == workbook.SHEET_UNITS and issue["column"] == "floor_code"
            for issue in report["issues"]
        ), _messages(report)
        assert db.scalars(select(Floor.code)).all() == []

    def test_the_same_phase_twice_is_a_duplicate_not_a_merge(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(phases=(PHASE, {"phase_code": "PHASE-1", "phase_name": "Phase One"})),
        )

        assert report["error_count"] == 1
        assert report["issues"][0]["sheet"] == workbook.SHEET_PHASES
        assert "row 2" in report["issues"][0]["message"]

    def test_an_identical_duplicate_is_still_a_duplicate(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        """Silently keeping one of two identical rows hides the mistake.

        An operator who pasted a block twice needs to know they did.
        """
        report = _validate(admin_client, operational_project, _book(phases=(PHASE, dict(PHASE))))

        assert report["error_count"] == 1

    def test_two_buildings_with_one_code_in_one_phase_collide(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(phases=(PHASE,), buildings=(BUILDING, {**BUILDING, "building_name": "Other"})),
        )

        assert report["error_count"] == 1
        assert report["issues"][0]["column"] == "building_code"

    def test_the_same_building_code_in_two_phases_is_two_buildings(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """B1 in Phase 1 and B1 in Phase 2 are different buildings.

        The domain scopes a building code to its phase, so refusing this would
        be the importer inventing a rule the rest of the system does not have.
        """
        report = _apply(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE, {"phase_code": "PHASE-2", "phase_name": "Phase 2"}),
                buildings=(BUILDING, {**BUILDING, "phase_code": "PHASE-2"}),
            ),
        )

        assert report["applied"] is True, _messages(report)
        assert sorted(db.scalars(select(Building.code))) == ["B1", "B1"]

    def test_two_floors_with_one_code_in_one_building_collide(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(FLOOR, {**FLOOR, "floor_label": "Other"}),
            ),
        )

        assert report["error_count"] == 1
        assert report["issues"][0]["column"] == "floor_code"

    def test_the_same_floor_code_in_two_buildings_is_two_floors(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _apply(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(
                    BUILDING,
                    {**BUILDING, "building_code": "B2", "building_name": "Building 2"},
                ),
                floors=(FLOOR, {**FLOOR, "building_code": "B2"}),
            ),
        )

        assert report["applied"] is True, _messages(report)
        assert sorted(db.scalars(select(Floor.code))) == ["01", "01"]

    def test_a_floor_code_keeps_the_text_a_building_actually_uses(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """B2, GF and RF are floor codes. An integer cannot hold them."""
        report = _apply(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(
                    {**FLOOR, "floor_code": "B1", "floor_label": "Basement 1", "level_number": -1},
                    {**FLOOR, "floor_code": "GF", "floor_label": "Ground floor", "level_number": 0},
                    {**FLOOR, "floor_code": "RF", "floor_label": "Roof", "level_number": 9},
                ),
            ),
        )

        assert report["applied"] is True, _messages(report)
        assert sorted(db.scalars(select(Floor.code))) == ["B1", "GF", "RF"]


# --------------------------------------------------------------------------- #
# A spreadsheet is data
# --------------------------------------------------------------------------- #


class TestNothingInAWorkbookIsExecuted:
    """The property that makes accepting spreadsheets acceptable.

    An inventory import is data capture. A workbook that arrives with formulas
    in it is refused rather than resolved, and the value the last version of
    Excel happened to cache is never read — that number was computed by
    something nobody here has seen, from inputs nobody here can check.
    """

    def test_a_formula_in_a_data_cell_refuses_the_workbook(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        def put_a_formula(book: Workbook) -> None:
            book[workbook.SHEET_PHASES]["B2"] = "=1+1"

        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(phases=(PHASE,), edit=put_a_formula),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text
        assert "formula" in response.json()["detail"].lower()
        # And emphatically not the number two.
        assert response.json()["detail"] != "2"

    def test_the_cached_value_of_a_formula_is_never_read(self) -> None:
        """Proved on the loader rather than through the API.

        ``data_only=True`` would hand back whatever Excel last calculated, and
        the parse would import it as though somebody had typed it. This asserts
        the parser sees the formula text — which is what lets it refuse.
        """
        body = _book(
            phases=(PHASE,), edit=lambda book: book[workbook.SHEET_PHASES].__setitem__("B2", "=1+1")
        )
        book = load_workbook(io.BytesIO(body), read_only=True, data_only=False)
        try:
            assert workbook._is_formula(book[workbook.SHEET_PHASES]["B2"])
        finally:
            book.close()

    def test_a_formula_in_a_header_refuses_the_workbook(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(edit=lambda book: book[workbook.SHEET_UNITS].__setitem__("A1", "=A2")),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text

    def test_a_macro_enabled_workbook_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        body = _book(phases=(PHASE,))
        with_macro = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(body)) as source,
            zipfile.ZipFile(with_macro, "w") as target,
        ):
            for entry in source.infolist():
                target.writestr(entry, source.read(entry.filename))
            target.writestr("xl/vbaProject.bin", b"\x00\x01\x02")

        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=with_macro.getvalue(),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text
        assert "macro" in response.json()["detail"].lower()

    def test_a_file_that_is_not_a_workbook_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=b"phase_code,phase_name\nPHASE-1,Phase 1\n",
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text

    def test_a_password_protected_workbook_says_so(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        """An encrypted .xlsx is an OLE2 container, not a ZIP.

        Left to the ZIP reader it produces "not a readable workbook", which
        sends an operator to rebuild a file that is fine.
        """
        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512,
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text
        assert "password" in response.json()["detail"].lower()

    def test_a_file_over_the_bound_is_refused_before_it_is_parsed(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=b"\x00" * (workbook.MAX_BYTES + 1),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text

    def test_an_oversized_archive_is_refused_before_anything_is_decompressed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The order is the security property, not the eventual refusal.

        An earlier version called ``ZipFile.testzip()`` first — which
        decompresses every member to check its CRC — and compared the
        uncompressed total afterwards. It expanded the bomb in order to decide
        whether it was too big to expand, and the previous version of this test
        could not tell: it asserted only that the refusal eventually happened.

        So this one instruments the decompressing calls and fails if either is
        reached. The bound is patched small so the archive stays small; the real
        constant is checked separately below.
        """
        bomb = io.BytesIO()
        with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", b"\x00" * 4096)
        body = bomb.getvalue()

        # Patched only after the archive exists: writestr goes through
        # ZipFile.open too, and patching first would have failed the test on
        # its own fixture rather than on the code under test.
        monkeypatch.setattr(workbook, "MAX_UNCOMPRESSED", 1024)

        def never(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("the archive was decompressed before its size was judged")

        monkeypatch.setattr(zipfile.ZipFile, "testzip", never)
        monkeypatch.setattr(zipfile.ZipFile, "open", never)

        with pytest.raises(workbook.WorkbookRefused, match="expands to far more"):
            workbook._archive_is_safe(body)

    def test_an_archive_that_understates_itself_cannot_over_deliver(self) -> None:
        """The declared size is a claim, so what happens when it lies matters.

        Checked against CPython rather than asserted from reasoning:
        ``ZipExtFile`` bounds each read by the declared ``file_size`` and then
        raises ``BadZipFile`` on the CRC mismatch. So an understating archive
        truncates and fails — it cannot deliver more than the central directory
        was judged on, which is what makes the directory check the real gate.

        This test exists because the fix's first docstring claimed the
        opposite, and a security note that is merely plausible is worth no more
        than the one it replaced.
        """
        import copy

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", b"\x00" * 65536)

        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
            honest = archive.infolist()[0]
            lying = copy.copy(honest)
            lying.file_size = 16
            with pytest.raises(zipfile.BadZipFile), archive.open(lying) as member:
                member.read()

    def test_the_uncompressed_bound_is_larger_than_the_one_on_the_wire(self) -> None:
        """A workbook is a ZIP, so the size on the wire is not the size in memory."""
        assert workbook.MAX_UNCOMPRESSED > workbook.MAX_BYTES
        assert workbook.MAX_UNCOMPRESSED == 64 * 1024 * 1024


class TestTheTemplateVersionIsAContract:
    def test_an_unknown_version_is_refused_by_name(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(phases=(PHASE,), version="inventory_structure_v99"),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert "inventory_structure_v99" in detail
        assert workbook.TEMPLATE_VERSION in detail

    def test_a_blank_version_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(phases=(PHASE,), version=""),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text

    def test_the_accepted_version_is_reported_back(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(admin_client, operational_project, _book(phases=(PHASE,)))

        assert report["template_version"] == workbook.TEMPLATE_VERSION

    def test_a_renamed_sheet_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        def rename(book: Workbook) -> None:
            book[workbook.SHEET_FLOORS].title = "Levels"

        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(edit=rename),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text
        assert workbook.SHEET_FLOORS in response.json()["detail"]

    def test_a_renamed_column_is_refused_rather_than_guessed_at(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        def rename(book: Workbook) -> None:
            book[workbook.SHEET_PHASES]["A1"] = "phase"

        response = admin_client.post(
            f"{inventory_url(operational_project)}/import/workbook/validate?mode=create",
            content=_book(edit=rename),
            headers={"Content-Type": XLSX},
        )

        assert response.status_code == 422, response.text
        assert "phase_code" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Fields, modes, and the transaction
# --------------------------------------------------------------------------- #


class TestFieldsAreJudgedByTheDomain:
    def test_an_asset_class_the_domain_does_not_have_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(FLOOR,),
                units=(_unit("101", "B1-101", asset_class="spaceship"),),
            ),
        )

        assert report["error_count"] >= 1
        assert any(issue["sheet"] == workbook.SHEET_UNITS for issue in report["issues"])

    def test_a_phase_status_the_domain_does_not_have_is_refused_by_name(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client, operational_project, _book(phases=({**PHASE, "status": "nearly"},))
        )

        assert report["error_count"] == 1
        assert report["issues"][0]["column"] == "status"
        assert "planning" in report["issues"][0]["message"]

    def test_a_date_in_another_locale_is_refused_rather_than_guessed(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        """03/04/2026 is April in one country and March in another.

        Picking one would silently move a phase's planned start by a month.
        """
        report = _validate(
            admin_client,
            operational_project,
            _book(phases=({**PHASE, "planned_start": "03/04/2026"},)),
        )

        assert report["error_count"] == 1
        assert report["issues"][0]["column"] == "planned_start"
        assert workbook.DATE_FORMAT in report["issues"][0]["message"]

    def test_an_iso_date_is_stored(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _apply(
            admin_client,
            operational_project,
            _book(phases=({**PHASE, "planned_start": "2026-04-20", "status": "active"},)),
        )

        assert report["applied"] is True, _messages(report)
        phase = db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one()
        assert phase.planned_start.isoformat() == "2026-04-20"
        assert phase.status == "active"

    def test_a_real_date_cell_is_read_as_a_date_not_a_timestamp(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        from datetime import datetime

        report = _apply(
            admin_client,
            operational_project,
            _book(phases=({**PHASE, "planned_start": datetime(2026, 4, 20, 0, 0)},)),
        )

        assert report["applied"] is True, _messages(report)
        phase = db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one()
        assert phase.planned_start.isoformat() == "2026-04-20"

    def test_a_blank_optional_cell_writes_nothing(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))

        phase = db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one()
        assert phase.notes is None
        assert phase.planned_start is None

    def test_a_missing_required_cell_names_the_column(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client, operational_project, _book(phases=({"phase_code": "PHASE-1"},))
        )

        assert report["error_count"] == 1
        assert report["issues"][0]["column"] == "phase_name"


class TestCreateAndUpsert:
    def test_create_mode_refuses_a_code_that_already_exists(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))

        report = _validate(admin_client, operational_project, _book(phases=(PHASE,)), mode="create")

        assert report["error_count"] == 1
        assert "create mode" in report["issues"][0]["message"]

    def test_upsert_updates_what_the_code_names(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))

        report = _apply(
            admin_client,
            operational_project,
            _book(phases=({**PHASE, "phase_name": "Phase One, renamed", "status": "active"},)),
            mode="upsert",
        )

        assert report["applied"] is True, _messages(report)
        assert report["structure"]["records"]["phases"] == {"create": 0, "update": 1}
        phase = db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one()
        assert phase.name == "Phase One, renamed"
        assert phase.status == "active"
        assert db.scalars(select(Phase.id)).all() == [phase.id]

    def test_upsert_leaves_the_code_alone(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """A code is identity. An import updates what a record says, not which record it is."""
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))
        before = db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one().id

        _apply(
            admin_client,
            operational_project,
            _book(phases=({**PHASE, "phase_name": "Renamed"},)),
            mode="upsert",
        )

        assert db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one().id == before


class TestOneWorkbookIsOneTransaction:
    def test_validation_writes_nothing(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(FLOOR,),
                units=(_unit("101", "B1-101"),),
            ),
        )

        assert report["applied"] is False
        assert report["error_count"] == 0, _messages(report)
        assert db.scalars(select(Phase.id)).all() == []
        assert db.scalars(select(Unit.id)).all() == []

    def test_apply_reads_the_bytes_again_and_does_not_trust_an_earlier_validate(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """A clean validate is not a token that unlocks apply.

        The file on the operator's disk can change between the two calls, and a
        caller can send any summary it likes.
        """
        clean = _book(phases=(PHASE,))
        assert _validate(admin_client, operational_project, clean)["error_count"] == 0

        broken = _book(phases=(PHASE, dict(PHASE)))
        report = _apply(admin_client, operational_project, broken)

        assert report["applied"] is False
        assert report["error_count"] == 1
        assert db.scalars(select(Phase.id)).all() == []

    def test_a_failure_while_writing_units_takes_the_whole_workbook_with_it(
        self,
        admin_client: TestClient,
        operational_project: str,
        db: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The interesting failure is the late one.

        Phases, buildings and floors are written before the first unit. If the
        unit write then fails, every one of them has to go — a development
        holding three floors and none of its units is a catalogue nobody can
        reason about, and it looks exactly like a successful import of a
        smaller file.
        """
        from app.modules.inventory import import_service

        def fail_late(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("row 247 of 247")

        monkeypatch.setattr(import_service, "apply_rows", fail_late)

        # Re-raised rather than swallowed: a batch that failed must look like a
        # batch that failed. A rollback that returned quietly would leave the
        # operator reading a success and believing three floors exist.
        with pytest.raises(RuntimeError, match="row 247"):
            admin_client.post(
                f"{inventory_url(operational_project)}/import/workbook/apply?mode=create",
                content=_book(
                    phases=(PHASE,),
                    buildings=(BUILDING,),
                    floors=(FLOOR,),
                    units=(_unit("101", "B1-101"),),
                ),
                headers={"Content-Type": XLSX},
            )

        assert db.scalars(select(Phase.id)).all() == []
        assert db.scalars(select(Building.id)).all() == []
        assert db.scalars(select(Floor.id)).all() == []
        assert db.scalars(select(Unit.id)).all() == []

    def test_one_workbook_writes_one_import_event_carrying_its_correlation(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        _apply(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=(FLOOR,),
                units=(_unit("101", "B1-101"),),
            ),
        )

        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "inventory.import_applied")
        ).all()
        assert len(events) == 1
        assert events[0].after_data["format"] == "workbook"
        assert events[0].after_data["template_version"] == workbook.TEMPLATE_VERSION
        assert events[0].correlation_id is not None


# --------------------------------------------------------------------------- #
# One domain, two ways in
# --------------------------------------------------------------------------- #


def _phases_url(project_id: str) -> str:
    return f"{inventory_url(project_id)}/phases"


class TestTheWorkbookIsJudgedByTheSameRulesAsTheForm:
    """A spreadsheet is an input adapter, not a second rulebook.

    Every test here pairs a value with the verdict the manual path gives it. The
    failure this guards against is quiet: a workbook that ``validate`` calls
    clean and ``apply`` then refuses, or worse, one that loads a record the form
    would never have accepted. Both were live before the mutation primitives
    existed, because the workbook wrote ORM rows directly and inherited none of
    the service's checks.
    """

    def test_a_code_the_form_refuses_is_refused_in_the_workbook_too(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        bad = "PHASE 1!"

        form = admin_client.post(_phases_url(operational_project), json={"code": bad, "name": "X"})
        report = _validate(
            admin_client,
            operational_project,
            _book(phases=({"phase_code": bad, "phase_name": "X"},)),
        )

        assert form.status_code >= 400, form.text
        assert report["error_count"] >= 1, _messages(report)
        assert any(issue["column"] == "phase_code" for issue in report["issues"]), _messages(report)

    def test_an_invalid_building_code_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(phases=(PHASE,), buildings=({**BUILDING, "building_code": "B 1*"},)),
        )

        assert any(issue["column"] == "building_code" for issue in report["issues"]), _messages(
            report
        )

    def test_an_invalid_floor_code_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,), buildings=(BUILDING,), floors=({**FLOOR, "floor_code": "0 1/"},)
            ),
        )

        assert any(issue["column"] == "floor_code" for issue in report["issues"]), _messages(report)

    def test_a_negative_sequence_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        """`ge=0` lives on the request model, and the workbook is judged by it."""
        report = _validate(
            admin_client, operational_project, _book(phases=({**PHASE, "sequence": -1},))
        )

        assert any(issue["column"] == "sequence" for issue in report["issues"]), _messages(report)

    def test_an_overlong_phase_name_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client, operational_project, _book(phases=({**PHASE, "phase_name": "N" * 201},))
        )

        assert any(issue["column"] == "phase_name" for issue in report["issues"]), _messages(report)

    def test_overlong_phase_notes_are_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client, operational_project, _book(phases=({**PHASE, "notes": "n" * 2001},))
        )

        assert any(issue["column"] == "notes" for issue in report["issues"]), _messages(report)

    @pytest.mark.parametrize("column", ["building_name", "zone", "block", "entrance_wing"])
    def test_an_overlong_building_field_is_refused(
        self, admin_client: TestClient, operational_project: str, column: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(phases=(PHASE,), buildings=({**BUILDING, column: "x" * 400},)),
        )

        assert report["error_count"] >= 1, f"{column}: {_messages(report)}"

    def test_an_overlong_floor_label_is_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(PHASE,),
                buildings=(BUILDING,),
                floors=({**FLOOR, "floor_label": "L" * 201},),
            ),
        )

        assert any(issue["column"] == "floor_label" for issue in report["issues"]), _messages(
            report
        )

    def test_phase_dates_out_of_order_are_refused(
        self, admin_client: TestClient, operational_project: str
    ) -> None:
        report = _validate(
            admin_client,
            operational_project,
            _book(
                phases=(
                    {**PHASE, "planned_start": "2026-06-01", "planned_completion": "2026-01-01"},
                )
            ),
        )

        assert any(issue["column"] == "planned_completion" for issue in report["issues"]), (
            _messages(report)
        )

    def test_a_building_cannot_be_loaded_under_a_retired_phase(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """A spreadsheet is not an administrative bypass.

        `stage_create_building` refuses an inactive parent. Validate asks the
        same question early, so the operator reads it beside the row instead of
        meeting it as a failed apply.
        """
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))
        phase = db.scalars(select(Phase).where(Phase.code == "PHASE-1")).one()
        retire = admin_client.patch(
            f"{_phases_url(operational_project)}/{phase.id}", json={"is_active": False}
        )
        assert retire.status_code == 200, retire.text

        report = _validate(admin_client, operational_project, _book(buildings=(BUILDING,)))

        assert report["error_count"] >= 1, _messages(report)
        assert any("not active" in issue["message"] for issue in report["issues"]), _messages(
            report
        )
        assert db.scalars(select(Building.id)).all() == []

    def test_a_floor_cannot_be_loaded_under_a_retired_building(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        _apply(admin_client, operational_project, _book(phases=(PHASE,), buildings=(BUILDING,)))
        building = db.scalars(select(Building).where(Building.code == "B1")).one()
        retire = admin_client.patch(
            f"{inventory_url(operational_project)}/buildings/{building.id}",
            json={"is_active": False},
        )
        assert retire.status_code == 200, retire.text

        report = _validate(admin_client, operational_project, _book(floors=(FLOOR,)))

        assert report["error_count"] >= 1, _messages(report)
        assert any("not active" in issue["message"] for issue in report["issues"]), _messages(
            report
        )
        assert db.scalars(select(Floor.id)).all() == []

    def test_an_upsert_writes_the_same_audit_the_form_writes(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        """The audit has to say what changed, not merely that something did.

        The workbook used to write its own abbreviated event carrying a code and
        a name. "Phase status changed from planning to active" was unavailable
        from it — which is the difference between an audit trail and a log line.
        """
        _apply(admin_client, operational_project, _book(phases=(PHASE,)))

        _apply(
            admin_client,
            operational_project,
            _book(phases=({**PHASE, "status": "active", "phase_name": "Phase One"},)),
            mode="upsert",
        )

        event = db.scalars(select(AuditEvent).where(AuditEvent.action == "phase.updated")).one()
        assert event.before_data["status"] == "planning"
        assert event.after_data["status"] == "active"
        assert event.before_data["name"] == "Phase 1"
        assert event.after_data["name"] == "Phase One"
        # The batch event complements the domain events; it does not replace them.
        assert db.scalars(
            select(AuditEvent).where(AuditEvent.action == "inventory.import_applied")
        ).all()
        assert event.correlation_id is not None

    def test_a_building_upsert_records_its_changed_fields(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        _apply(admin_client, operational_project, _book(phases=(PHASE,), buildings=(BUILDING,)))

        _apply(
            admin_client,
            operational_project,
            _book(buildings=({**BUILDING, "zone": "South", "block": "C", "sequence": 7},)),
            mode="upsert",
        )

        event = db.scalars(select(AuditEvent).where(AuditEvent.action == "building.updated")).one()
        assert event.before_data["zone"] is None
        assert event.after_data["zone"] == "South"
        assert event.after_data["block"] == "C"
        assert event.after_data["sequence"] == 7

    def test_a_floor_upsert_records_its_changed_fields(
        self, admin_client: TestClient, operational_project: str, db: Session
    ) -> None:
        _apply(
            admin_client,
            operational_project,
            _book(phases=(PHASE,), buildings=(BUILDING,), floors=(FLOOR,)),
        )

        _apply(
            admin_client,
            operational_project,
            _book(floors=({**FLOOR, "floor_label": "Level one", "level_number": 4},)),
            mode="upsert",
        )

        event = db.scalars(select(AuditEvent).where(AuditEvent.action == "floor.updated")).one()
        assert event.before_data["label"] == "First floor"
        assert event.after_data["label"] == "Level one"
        assert event.after_data["level_number"] == 4

    def test_the_workbook_module_owns_no_hierarchy_rules(self) -> None:
        """Read from the source, because "we moved it" is a claim about code.

        The point of the mutation primitives is that this module stopped being
        a second implementation. If it starts building ORM rows or writing
        hierarchy audit events again, it has started being one.
        """
        source = (
            __import__("pathlib")
            .Path("app/modules/inventory/workbook.py")
            .read_text(encoding="utf-8")
        )
        writer = source[source.index("def _write_hierarchy(") :]

        for forbidden in ("Phase(", "Building(", "Floor(", "record_event(", "session.add("):
            assert forbidden not in writer, f"_write_hierarchy still does {forbidden}"
        for required in (
            "stage_create_phase",
            "stage_update_phase",
            "stage_create_building",
            "stage_update_building",
            "stage_create_floor",
            "stage_update_floor",
        ):
            assert required in writer, required
