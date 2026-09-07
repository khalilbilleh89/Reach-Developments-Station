"""Physical completion cannot write any financial, legal or delivery source."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from tests.modules.conftest import construction_url


def test_completion_and_correction_leave_all_business_sources_unchanged(
    db: Session,
    manager_member_client: TestClient,
    project_id: str,
    unit_id: str,
    active_plan: tuple[str, str],
    active_contract: str,
    active_budget: str,
) -> None:
    """Seed a live sale/schedule and contractor commitment, not only empty tables.

    Compare every mapped business table, including invoice/certification,
    instalment triggers, collections, handover, status events and cost actuals.
    Only the new physical event and its audit record may change.
    """
    root = construction_url(project_id)
    client = manager_member_client
    stage = client.post(f"{root}/stages", json={"name": "Structure"}).json()["id"]
    excluded = {"unit_stage_events", "audit_events"}
    tables = {
        mapper.local_table.name: mapper.local_table
        for mapper in Base.registry.mappers
        if mapper.class_.__module__.startswith(
            (
                "app.modules.construction.",
                "app.modules.sales.",
                "app.modules.payment_plans.",
                "app.modules.collections.",
                "app.modules.inventory.",
                "app.modules.unit_economics.",
            )
        )
        and mapper.local_table.name not in excluded
    }

    def business_state() -> dict[str, list[str]]:
        return {
            name: sorted(repr(tuple(row)) for row in db.execute(select(table)))
            for name, table in tables.items()
        }

    before = business_state()
    path = f"{root}/units/{unit_id}/stages/{stage}/completion"
    for revision, day in enumerate(("2026-08-01", "2026-08-02", None)):
        response = client.post(
            path,
            json={
                "completed_date": day,
                "reason": "Site evidence / correction",
                "expected_revision": revision,
            },
        )
        assert response.status_code == 204, response.text
        assert business_state() == before
    progress = client.get(f"{root}/units/{unit_id}/stages").json()["stages"][0]
    assert progress["revision"] == 3
    assert len(progress["history"]) == 3
    assert progress["completed_date"] is None
