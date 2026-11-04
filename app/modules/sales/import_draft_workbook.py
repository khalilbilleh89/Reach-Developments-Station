"""A versioned, project-bound workbook covering Sales input sections.

Source assertions are validated and retained as review data, never posted events.
"""

import io
import json
import uuid
from datetime import date, datetime
from typing import Annotated

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import AwareDatetime, Field, create_model

from app.core.errors import ValidationError
from app.core.xlsx import check_archive
from app.modules.collections import schemas as collections
from app.modules.payment_plans import schemas as plans
from app.modules.sales import schemas as sales


class EoiInput(sales.StrictRequest):
    signed: bool | None = None
    occurred_at: AwareDatetime | None = None
    amount: sales.Money | None = None


class SaleInput(sales.StrictRequest):
    unit_reference: Annotated[str, Field(min_length=1, max_length=100)]
    client_id: uuid.UUID | None = None
    notes: sales.Notes | None = None


# Each sheet exposes every writable field in its owning input contract.
SPECS = {
    "Sales": (SaleInput, set()),
    "Buyer": (sales.ClientCreateRequest, set()),
    "Agent": (sales.SalesAgentCreateRequest, set()),
    "EOI": (EoiInput, set()),
    "Reservation": (
        sales.ReservationCreateRequest,
        {"unit_id", "client_id", "creation_request_id"},
    ),
    "SPA": (sales.SaleUpdateRequest, set()),
    "Parties": (sales.PartyCreateRequest, set()),
    "Adjustments": (sales.AdjustmentCreateRequest, set()),
    "Legal": (sales.LegalEventCreateRequest, set()),
    "Payment plan": (plans.PlanCreateRequest, {"sale_contract_id", "source_template_version_id"}),
    "Schedule": (plans.ScheduleWriteRequest, {"installments"}),
    "Installments": (plans.InstallmentWrite, set()),
    "Receipts": (collections.ReceiptCreate, set()),
    "Allocations": (collections.AllocationCreate, set()),
    "Collection actions": (collections.CollectionActionCreate, set()),
    "Disputes": (collections.DisputeCreate, set()),
    "Waivers": (collections.WaiverCreate, set()),
    "Refunds": (collections.RefundCreate, set()),
    "Cancellation": (sales.CancellationCreateRequest, set()),
    "Handover": (sales.HandoverUpdateRequest, set()),
}
SINGLE = {
    "Sales",
    "Buyer",
    "Agent",
    "EOI",
    "Reservation",
    "SPA",
    "Payment plan",
    "Schedule",
    "Cancellation",
    "Handover",
}
MODELS = {
    name: create_model(
        f"Draft{model.__name__}",
        __base__=sales.StrictRequest,
        **{
            key: (field.rebuild_annotation() | None, None)
            for key, field in model.model_fields.items()
            if key not in excluded
        },
    )
    for name, (model, excluded) in SPECS.items()
}
COLUMNS = {name: ["sale_key", *model.model_fields] for name, model in MODELS.items()}
MAX_SALES = 1000
MAX_ROWS = 10000


def validate_payload(payload: dict) -> dict:
    unknown = set(payload) - set(SPECS)
    if unknown:
        raise ValidationError("Unknown Sales sections: " + ", ".join(sorted(unknown)))
    if sum(len(rows) for rows in payload.values() if isinstance(rows, list)) > MAX_ROWS:
        raise ValidationError("Too many draft rows.")
    result = {}
    for name, rows in payload.items():
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValidationError(f"{name}: expected a bounded list of rows.")
        if name in SINGLE and len(rows) > 1:
            raise ValidationError(f"{name}: use one row per sale_key.")
        normalized = []
        for row in rows:
            if isinstance(row, dict):
                row = dict(row)
                for key, value in row.items():
                    if key.endswith("_json") and isinstance(value, str):
                        try:
                            row[key] = json.loads(value)
                        except ValueError as exc:
                            raise ValidationError(
                                f"{name}: {key} must contain valid JSON."
                            ) from exc
            normalized.append(row)
        result[name] = [
            MODELS[name].model_validate(row).model_dump(mode="json", exclude_none=True)
            for row in normalized
        ]
    root = result.get("Sales", [])
    if len(root) != 1 or not root[0].get("unit_reference"):
        raise ValidationError("Sales: enter the unit_reference.")
    if not root[0].get("client_id") and not (result.get("Buyer") or [{}])[0].get("display_name"):
        raise ValidationError("Enter an existing client_id or a Buyer display_name.")
    eoi = (result.get("EOI") or [{}])[0]
    if eoi and set(eoi) != {"signed", "occurred_at", "amount"}:
        raise ValidationError("EOI: enter signed, occurred_at with timezone, and amount together.")
    return result


def template(project_id: str, drafts: list[tuple[str, dict]] | None = None) -> bytes:
    book = Workbook()
    notes = book.active
    notes.title = "Instructions"
    for row in [
        ["Template", "sales_drafts_v1"],
        ["Project", project_id],
        [
            "Workflow",
            (
                "Fill Sales, then the relevant section sheets. Validate, save drafts, "
                "review, then add reviewed drafts to Sales."
            ),
        ],
        [
            "Link rows",
            (
                "Use the same unique sale_key in each sheet. Repeat it for multiple "
                "parties, installments, receipts or legal events. Maximum 1,000 sales "
                "and 10,000 data rows total."
            ),
        ],
        [
            "Draft only",
            (
                "No unit hold, legal attestation, approved payment schedule, or "
                "confirmed receipt is created by importing."
            ),
        ],
        [
            "Adding to Sales",
            (
                "Adds a preparing transaction with buyer, agent, parties and "
                "reservation terms. All other supplied sections stay attached as "
                "unposted review evidence; complete the normal "
                "SPA/legal/payment/handover workflows explicitly."
            ),
        ],
        [
            "Input",
            (
                "Use plain values, never formulas. Dates YYYY-MM-DD; timestamps include"
                " timezone, e.g. 2026-11-02T09:30:00+02:00. Money uses decimal text, "
                "not currency symbols. Fractions: 0.05 means 5%."
            ),
        ],
        [
            "References",
            (
                "Copy unit_reference and existing client_id from the reference sheets. "
                "Blank optional sections are allowed. Existing buyers/agents are never "
                "silently edited."
            ),
        ],
        [
            "Files",
            (
                "Document fields hold references, not binary attachments. Upload signed"
                " documents and evidence through their normal record screens."
            ),
        ],
        [
            "Corrections",
            (
                "Re-importing identical sale_key/details is skipped. Changed keys are "
                "refused: edit the existing draft, or delete it and import the "
                "corrected workbook. Added source records are retained."
            ),
        ],
        [
            "Computed fields",
            (
                "Totals, balances, approval identities and live statuses are derived by"
                " the application, never imported as authoritative figures."
            ),
        ],
    ]:
        notes.append(row)
    guide = book.create_sheet("Field guide")
    guide.append(["Sheet", "Column", "Meaning", "Type and allowed values"])
    for name, model in MODELS.items():
        sheet = book.create_sheet(name)
        sheet.append(COLUMNS[name])
        schema = model.model_json_schema()
        for key in model.model_fields:
            guide.append(
                [
                    name,
                    key,
                    key.replace("_", " "),
                    json.dumps(schema["properties"][key], ensure_ascii=False),
                ]
            )
        for key, payload in drafts or []:
            for row in payload.get(name, []):
                sheet.append(
                    [
                        key,
                        *[
                            json.dumps(row[column], ensure_ascii=False)
                            if isinstance(row.get(column), (dict, list))
                            else row.get(column)
                            for column in COLUMNS[name][1:]
                        ],
                    ]
                )
        for row in sheet.iter_rows(
            min_row=2, max_row=max(101, sheet.max_row), max_col=len(COLUMNS[name])
        ):
            for cell in row:
                cell.number_format = "@"
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    for sheet in book:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="173F42")
        for index in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(index)].width = 30
    notes.column_dimensions["B"].width = 110
    stream = io.BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def parse(body: bytes, project_id: str) -> list[tuple[int, str, dict]]:
    check_archive(body)
    try:
        book = load_workbook(io.BytesIO(body), read_only=True, data_only=False, keep_links=False)
    except Exception as exc:
        raise ValidationError("Choose a readable .xlsx workbook.") from exc
    try:
        if (
            "Instructions" not in book
            or book["Instructions"]["B1"].value != "sales_drafts_v1"
            or book["Instructions"]["B2"].value != project_id
        ):
            raise ValidationError(
                "Download this project's Sales draft template; its version or project "
                "does not match."
            )
        allowed = set(COLUMNS) | {
            "Instructions",
            "Field guide",
            "Unit reference",
            "Buyer reference",
            "Agent reference",
        }
        if set(book.sheetnames) - allowed:
            raise ValidationError("Unknown worksheet; use the project template sections.")
        data: dict[str, dict] = {}
        positions = {}
        count = 0
        for name, columns in COLUMNS.items():
            if name not in book:
                raise ValidationError(f"Missing sheet: {name}.")
            sheet = book[name]
            sheet.reset_dimensions()
            iterator = sheet.iter_rows()
            headers = [str(cell.value or "").strip() for cell in next(iterator, ())]
            while headers and not headers[-1]:
                headers.pop()
            if sorted(headers) != sorted(columns):
                raise ValidationError(f"{name}: keep each template header exactly once.")
            for number, cells in enumerate(iterator, 2):
                if number > MAX_ROWS + 1000:
                    raise ValidationError(f"{name}: too many worksheet rows.")
                values = {}
                for index, cell in enumerate(cells):
                    value = cell.value
                    if cell.data_type in {"f", "e"} or (
                        isinstance(value, str) and value.startswith("=")
                    ):
                        raise ValidationError(
                            f"{name} row {number}: formulas and Excel errors are not allowed."
                        )
                    if value is None or value == "":
                        continue
                    if index >= len(headers):
                        raise ValidationError(
                            f"{name} row {number}: data outside template columns."
                        )
                    key = headers[index]
                    if isinstance(value, datetime):
                        value = (
                            value.isoformat() if key.endswith("_at") else value.date().isoformat()
                        )
                    elif isinstance(value, date):
                        value = value.isoformat()
                    elif isinstance(value, (int, float)):
                        value = str(value)
                    elif isinstance(value, str):
                        value = value.strip()
                    if key.endswith("_json") and isinstance(value, str):
                        value = json.loads(value)
                    values[key] = value
                if not values:
                    continue
                count += 1
                if count > MAX_ROWS:
                    raise ValidationError("Use at most 10,000 total data rows.")
                key = str(values.pop("sale_key", "")).strip()
                if not key or len(key) > 100:
                    raise ValidationError(
                        f"{name} row {number}: enter a sale_key up to 100 characters."
                    )
                if name == "Sales":
                    if key in positions:
                        raise ValidationError(f"Sales row {number}: repeated sale_key {key}.")
                    positions[key] = number
                data.setdefault(key, {}).setdefault(name, []).append(values)
        if not positions or len(positions) > MAX_SALES:
            raise ValidationError("Enter between 1 and 1,000 Sales rows.")
        if set(data) != set(positions):
            raise ValidationError("A section row refers to a sale_key absent from Sales.")
        return [(positions[key], key, payload) for key, payload in data.items()]
    except (KeyError, ValueError, TypeError) as exc:
        raise ValidationError(
            "Unreadable workbook values; use the project template and plain values."
        ) from exc
    finally:
        book.close()
