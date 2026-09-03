"""Delivery status: construction moves the build, sales moves the handover.

Three properties. Construction owns exactly three values and cannot reach the
handover states above them. Every write goes through inventory's public
contract, so the append-only status event exists whoever asked for the change.
And a bulk action is proved against every unit before any of them moves, because
a building left in two states is worse than a refusal.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Unit, UnitStatusEvent
from tests.modules.conftest import construction_url, inventory_url, unit_payload


def delivery_status(client: TestClient, project_id: str, unit_id: str) -> str:
    response = client.get(f"{inventory_url(project_id)}/units/{unit_id}")
    assert response.status_code == 200, response.text
    return response.json()["delivery_status"]


class TestConstructionOwnsThreeStates:
    def test_a_unit_can_be_started_and_made_ready(
        self,
        manager_member_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        unit_id: str,
    ) -> None:
        """Given / When / Then: not_started to under_construction to ready."""
        assert delivery_status(admin_client, project_id, unit_id) == "not_started"

        started = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"unit_id": unit_id, "effective_date": "2026-02-01"},
        )
        assert started.status_code == 200, started.text
        assert started.json() == {
            "to_status": "under_construction",
            "unit_count": 1,
            "unit_ids": [unit_id],
        }
        assert delivery_status(admin_client, project_id, unit_id) == "under_construction"

        ready = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/ready",
            json={"unit_id": unit_id, "effective_date": "2026-08-01"},
        )
        assert ready.status_code == 200, ready.text
        assert delivery_status(admin_client, project_id, unit_id) == "ready"

    def test_readiness_can_be_revoked_with_a_reason(
        self,
        manager_member_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        unit_id: str,
    ) -> None:
        for action, day in (("start", "2026-02-01"), ("ready", "2026-08-01")):
            response = manager_member_client.post(
                f"{construction_url(project_id)}/delivery/{action}",
                json={"unit_id": unit_id, "effective_date": day},
            )
            assert response.status_code == 200, response.text

        without_reason = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/revoke-ready",
            json={"unit_id": unit_id, "effective_date": "2026-08-15"},
        )
        assert without_reason.status_code == 422, without_reason.text

        revoked = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/revoke-ready",
            json={
                "unit_id": unit_id,
                "effective_date": "2026-08-15",
                "reason": "Snagging list reopened after inspection",
            },
        )
        assert revoked.status_code == 200, revoked.text
        assert delivery_status(admin_client, project_id, unit_id) == "under_construction"

    def test_construction_cannot_reach_a_handover_state(
        self,
        manager_member_client: TestClient,
        db: Session,
        project_id: str,
        unit_id: str,
    ) -> None:
        """Handover belongs to sales. Construction stops at ready."""
        unit = db.scalars(select(Unit).where(Unit.id == unit_id)).one()
        unit.delivery_status = "handed_over"
        db.commit()

        refused = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"unit_id": unit_id, "effective_date": "2026-09-01"},
        )
        assert refused.status_code == 409, refused.text
        assert "handover state" in refused.json()["detail"]

        db.refresh(unit)
        assert unit.delivery_status == "handed_over"


class TestEveryWriteLeavesAnEvent:
    def test_construction_writes_through_inventorys_contract(
        self,
        manager_member_client: TestClient,
        db: Session,
        project_id: str,
        unit_id: str,
    ) -> None:
        """The append-only event exists whoever asked for the change."""
        started = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={
                "unit_id": unit_id,
                "effective_date": "2026-02-01",
                "reason": "Substructure begun",
            },
        )
        assert started.status_code == 200, started.text

        events = list(
            db.scalars(
                select(UnitStatusEvent)
                .where(UnitStatusEvent.unit_id == unit_id, UnitStatusEvent.dimension == "delivery")
                .order_by(UnitStatusEvent.effective_date)
            )
        )
        assert len(events) == 1
        assert events[0].from_status == "not_started"
        assert events[0].to_status == "under_construction"
        assert events[0].reason == "Substructure begun"


class TestBulkIsAllOrNothing:
    def test_a_building_moves_as_one(
        self,
        manager_member_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        building_id: str,
        floor_id: str,
        unit_id: str,
    ) -> None:
        second = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="102", unit_reference="B1-102"),
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]

        started = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"building_id": building_id, "effective_date": "2026-02-01"},
        )
        assert started.status_code == 200, started.text
        assert started.json()["unit_count"] == 2
        assert delivery_status(admin_client, project_id, unit_id) == "under_construction"
        assert delivery_status(admin_client, project_id, second_id) == "under_construction"

    def test_one_blocked_unit_stops_the_whole_building(
        self,
        manager_member_client: TestClient,
        admin_client: TestClient,
        db: Session,
        project_id: str,
        building_id: str,
        floor_id: str,
        unit_id: str,
    ) -> None:
        """Given / When / Then: eighty-seven moved and one refused is the failure."""
        second = admin_client.post(
            f"{inventory_url(project_id)}/units",
            json=unit_payload(floor_id, unit_number="103", unit_reference="B1-103"),
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]

        blocked = db.scalars(select(Unit).where(Unit.id == second_id)).one()
        blocked.delivery_status = "handed_over"
        db.commit()

        refused = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"building_id": building_id, "effective_date": "2026-02-01"},
        )
        assert refused.status_code == 409, refused.text
        assert "none of it was" in refused.json()["detail"]
        assert delivery_status(admin_client, project_id, unit_id) == "not_started"

    def test_naming_two_scopes_at_once_is_refused(
        self,
        manager_member_client: TestClient,
        project_id: str,
        building_id: str,
        unit_id: str,
    ) -> None:
        refused = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={
                "unit_id": unit_id,
                "building_id": building_id,
                "effective_date": "2026-02-01",
            },
        )
        assert refused.status_code == 422, refused.text

    def test_an_empty_scope_is_refused_rather_than_answered_with_zero(
        self,
        manager_member_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        phase_id: str,
    ) -> None:
        """Nothing to move is a question, not a success."""
        empty = admin_client.post(
            f"{inventory_url(project_id)}/phases",
            json={"code": "PH-EMPTY", "name": "Nothing here yet", "sequence": 9},
        )
        assert empty.status_code == 201, empty.text
        refused = manager_member_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"phase_id": empty.json()["id"], "effective_date": "2026-02-01"},
        )
        assert refused.status_code == 404, refused.text


class TestWhoMayMoveTheBuild:
    def test_an_advisor_may_not_move_a_unit_through_construction(
        self, advisor_client: TestClient, project_id: str, unit_id: str
    ) -> None:
        refused = advisor_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"unit_id": unit_id, "effective_date": "2026-02-01"},
        )
        assert refused.status_code == 403, refused.text

    def test_design_engineering_may(
        self,
        engineer_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        unit_id: str,
    ) -> None:
        """The people running the build are the people who report its progress."""
        started = engineer_client.post(
            f"{construction_url(project_id)}/delivery/start",
            json={"unit_id": unit_id, "effective_date": "2026-02-01"},
        )
        assert started.status_code == 200, started.text
        assert delivery_status(admin_client, project_id, unit_id) == "under_construction"
