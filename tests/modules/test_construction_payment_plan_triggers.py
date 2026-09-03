"""The one path by which a construction event moves a buyer's money.

A milestone being *certified* — not forecast, not reported achieved — is what
makes an instalment waiting on it fall due, on the certified date. The two
halves are one transaction, and the dependency runs one way: construction calls
payment plans' public contract, and payment plans never imports construction.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    construction_url,
    create_milestone,
    current_version_id,
    fixed_row,
    plans_url,
    write_schedule,
)


def milestone_row(sequence: int, fraction: str, code: str, **overrides: object) -> dict[str, Any]:
    """One instalment falling due when a construction milestone is certified."""
    row: dict[str, Any] = {
        "sequence": sequence,
        "label": f"On {code}",
        "trigger_type": "construction_milestone",
        "trigger_reference": code,
        "principal_fraction": fraction,
    }
    row.update(overrides)
    return row


def plan_on_milestone(
    collections_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    plan_id: str,
    code: str,
) -> tuple[str, str]:
    """An active plan whose second instalment waits on ``code``."""
    version_id = current_version_id(collections_client, project_id, plan_id)
    written = write_schedule(
        collections_client,
        project_id,
        plan_id,
        version_id,
        [
            fixed_row(1, "0.200000", "2026-03-01"),
            milestone_row(2, "0.300000", code),
            fixed_row(3, "0.500000", "2026-09-01"),
        ],
    )
    assert written.status_code == 200, written.text
    base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
    assert collections_client.post(f"{base}/submit", json={}).status_code == 200
    approved = cfo_client.post(f"{base}/approve", json={"reason": "Terms reviewed"})
    assert approved.status_code == 200, approved.text
    activated = cfo_client.post(f"{base}/activate", json={})
    assert activated.status_code == 200, activated.text
    return plan_id, version_id


def installments(client: TestClient, project_id: str, plan_id: str) -> list[dict[str, Any]]:
    response = client.get(f"{plans_url(project_id)}/{plan_id}")
    assert response.status_code == 200, response.text
    return response.json()["current"]["installments"]


class TestCertificationTriggersTheInstalment:
    def test_an_instalment_waiting_on_a_milestone_falls_due_when_it_is_certified(
        self,
        manager_member_client: TestClient,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        plan_id: str,
        active_budget: str,
    ) -> None:
        """Given / When / Then: certified on the 2nd, due on the 2nd."""
        milestone = create_milestone(manager_member_client, project_id)
        assert milestone.status_code == 201, milestone.text
        plan_on_milestone(collections_client, cfo_client, project_id, plan_id, "FOUNDATION")

        before = installments(collections_client, project_id, plan_id)
        waiting = next(row for row in before if row["sequence"] == 2)
        assert waiting["trigger_status"] == "awaiting"

        certified = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone.json()['id']}/certify",
            json={"certified_date": "2026-05-02", "evidence_reference": "IPC-04"},
        )
        assert certified.status_code == 200, certified.text
        assert certified.json()["triggered_installment_count"] == 1
        assert certified.json()["triggered_plan_count"] == 1

        after = installments(collections_client, project_id, plan_id)
        triggered = next(row for row in after if row["sequence"] == 2)
        assert triggered["trigger_status"] == "triggered"
        assert triggered["triggered_due_date"] == "2026-05-02"

    def test_achieving_the_milestone_triggers_nothing(
        self,
        manager_member_client: TestClient,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        plan_id: str,
        active_budget: str,
    ) -> None:
        """Site reporting completion is information, not a buyer's due date."""
        milestone = create_milestone(manager_member_client, project_id)
        plan_on_milestone(collections_client, cfo_client, project_id, plan_id, "FOUNDATION")

        achieved = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone.json()['id']}/achieve",
            json={"achieved_date": "2026-05-01"},
        )
        assert achieved.status_code == 200, achieved.text

        rows = installments(collections_client, project_id, plan_id)
        assert next(row for row in rows if row["sequence"] == 2)["trigger_status"] == "awaiting"

    def test_a_milestone_no_plan_waits_on_triggers_nothing(
        self,
        manager_member_client: TestClient,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        plan_id: str,
        active_budget: str,
    ) -> None:
        assert create_milestone(manager_member_client, project_id).status_code == 201
        other = create_milestone(manager_member_client, project_id, code="TOPOUT", name="Top out")
        assert other.status_code == 201, other.text
        plan_on_milestone(collections_client, cfo_client, project_id, plan_id, "FOUNDATION")

        certified = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{other.json()['id']}/certify",
            json={"certified_date": "2026-05-02"},
        )
        assert certified.status_code == 200, certified.text
        assert certified.json()["triggered_installment_count"] == 0

        rows = installments(collections_client, project_id, plan_id)
        assert next(row for row in rows if row["sequence"] == 2)["trigger_status"] == "awaiting"


class TestTheSelectorFeedsTheReference:
    def test_the_code_a_plan_stores_is_a_code_the_selector_offered(
        self,
        manager_member_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """The selector exists so a trigger reference is not a free-text guess."""
        assert create_milestone(manager_member_client, project_id).status_code == 201
        options = collections_client.get(
            f"{construction_url(project_id)}/milestone-trigger-options"
        )
        assert options.status_code == 200, options.text
        assert [row["code"] for row in options.json()] == ["FOUNDATION"]


class TestTheDependencyRunsOneWay:
    def test_payment_plans_does_not_import_construction(self) -> None:
        import ast
        import pathlib

        imported: set[str] = set()
        for path in pathlib.Path("app/modules/payment_plans").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
        assert not [name for name in imported if "construction" in name]

    def test_construction_writes_no_instalment_column_itself(self) -> None:
        """Every write goes through the named contract, never a direct update."""
        import pathlib

        source = pathlib.Path("app/modules/construction/service.py").read_text()
        assert "PaymentPlanInstallment" not in source
        assert "apply_construction_milestone_certification" in source
