"""A newly added record creator must not silently omit its removal contract."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_record_creator_has_a_reviewed_deletion_contract() -> None:
    contracts = json.loads((ROOT / "docs/deletion_contracts.json").read_text(encoding="utf-8"))
    known_gaps = set(json.loads((ROOT / "tests/deletion_baseline_gaps.json").read_text()))
    indexed = {row["handler"]: row for row in contracts}
    assert len(indexed) == len(contracts), "Duplicate deletion contract"
    creators = {}
    for path in (ROOT / "app/modules").glob("*/api.py"):
        for function in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(function, ast.FunctionDef):
                continue
            created_response = any(
                isinstance(decorator, ast.Call)
                and any(
                    keyword.arg == "status_code"
                    and (
                        ast.unparse(keyword.value) == "201"
                        or "201_CREATED" in ast.unparse(keyword.value)
                    )
                    for keyword in decorator.keywords
                )
                for decorator in function.decorator_list
            )
            if not (
                function.name.startswith(("create_", "add_", "record_", "register_", "clone_"))
                or function.name
                in {"capture", "open_dispute", "submit_waiver", "start_cancellation"}
                or created_response
            ):
                continue
            for decorator in function.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {"post", "put"}
                ):
                    route = ast.literal_eval(decorator.args[0]) if decorator.args else ""
                    creators[f"{path.parent.name}.{function.name}"] = (
                        f"{decorator.func.attr.upper()} {route}"
                    )
    assert creators.keys() == indexed.keys(), (
        "Record creators changed: update docs/deletion_contracts.json and implement deletion. "
        f"Unreviewed: {creators.keys() - indexed.keys()}; stale: {indexed.keys() - creators.keys()}"
    )
    for name, route in creators.items():
        contract = indexed[name]
        assert contract["create_route"] == route
        assert contract["notes"].strip()
        assert contract["status"] in {"implemented", "retained", "missing"}
        if contract["status"] == "missing":
            assert name in known_gaps, f"New feature {name} has no deletion flow"
        elif contract["status"] == "retained":
            assert name in {
                "management_reporting.capture",
                "inventory.transition_unit",
                "payment_plans.submit_manual_trigger",
                "pricing.activate_escalation",
                "projects.transition_permit",
            }, "Retention needs explicit policy review"
        else:
            assert contract["removal_route"]
            assert (ROOT / contract["ui_file"]).is_file()


def test_inventory_removal_controls_call_the_api_and_reuse_confirmation() -> None:
    components = ROOT / "frontend/src/components/projects"
    for relative, call in (
        ("inventory/InventoryConfiguration.tsx", "inventory.deleteOption("),
        ("inventory/AreaTypesPanel.tsx", "inventory.deleteRecord("),
        ("inventory/unit/PhysicalRecord.tsx", "inventory.deleteRecord("),
        ("inventory/UnassignedAssets.tsx", "inventory.deleteRecord("),
    ):
        source = (components / relative).read_text(encoding="utf-8")
        assert "<DeleteRecordButton" in source
        assert call in source
        assert "onDeleted=" in source
    confirmation = (components / "DeleteRecordButton.tsx").read_text(encoding="utf-8")
    assert "<PromptDialog" in confirmation
    assert "await onDelete(reason)" in confirmation
    assert "await onDeleted()" in confirmation


def test_repository_instructions_and_pr_template_require_deletion() -> None:
    assert "docs/DELETION_POLICY.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    assert "Deletion coverage" in template
    assert "docs/deletion_contracts.json" in template
