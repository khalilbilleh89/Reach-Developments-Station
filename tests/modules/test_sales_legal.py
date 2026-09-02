"""The legal timeline: what the registry did, and who says so.

Append-only throughout. There is no route that edits a legal event and none that
deletes one, because a legal record that can be quietly overwritten is not a
legal record. A mistake is corrected by another dated, attributed event beside
the first.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    inventory_url,
    record_legal,
    sales_url,
    settle_and_clear_collections,
)


def _timeline(client: TestClient, project_id: str, sale_id: str) -> dict:
    response = client.get(f"{sales_url(project_id)}/contracts/{sale_id}/legal-events")
    assert response.status_code == 200, response.text
    return response.json()


def _legal_status(client: TestClient, project_id: str, unit_id: str) -> str:
    return client.get(f"{inventory_url(project_id)}/units/{unit_id}").json()["legal_status"]


def test_a_new_unit_starts_with_no_spa(
    admin_client: TestClient, project_id: str, unit_id: str
) -> None:
    """PR-MVP-03's ``not_started`` is this, named for the document it lacks."""
    assert _legal_status(admin_client, project_id, unit_id) == "no_spa"


def test_only_legal_may_record_a_legal_event(
    sales_ops_client: TestClient, legal_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    payload = {"event_type": "spa_drafted", "event_date": "2026-02-01"}
    url = f"{sales_url(project_id)}/contracts/{submitted_sale}/legal-events"

    refused = sales_ops_client.post(url, json=payload)
    allowed = legal_client.post(url, json=payload)

    assert refused.status_code == 403
    assert allowed.status_code == 201, allowed.text


def test_an_administrator_does_not_become_a_registrar(
    admin_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    response = admin_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/legal-events",
        json={"event_type": "spa_drafted", "event_date": "2026-02-01"},
    )

    assert response.status_code == 403


def test_the_unit_legal_status_follows_the_furthest_milestone(
    legal_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_sale: str,
    released_unit: str,
) -> None:
    record_legal(legal_client, project_id, active_sale, "land_registry_lodged", "2026-02-10")

    assert _legal_status(admin_client, project_id, released_unit) == "lodged_submitted"
    assert _timeline(legal_client, project_id, active_sale)["legal_status"] == "lodged_submitted"


def test_a_milestone_cannot_precede_what_it_depends_on(
    legal_client: TestClient, project_id: str, submitted_sale: str
) -> None:
    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{submitted_sale}/legal-events",
        json={"event_type": "registered", "event_date": "2026-02-01"},
    )

    assert response.status_code == 409
    assert "Record these first" in response.json()["detail"]


def test_the_same_milestone_cannot_be_recorded_twice(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "buyer_signed", "event_date": "2026-02-05"},
    )

    assert response.status_code == 409
    assert "already has a buyer signed event" in response.json()["detail"]


def test_an_event_cannot_be_dated_before_one_that_necessarily_preceded_it(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    """Signatures were recorded on the 3rd and 4th; lodging on the 1st is a fiction."""
    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "land_registry_lodged", "event_date": "2026-01-01"},
    )

    assert response.status_code == 422
    assert "cannot be dated before" in response.json()["detail"]


def test_an_event_cannot_be_dated_in_the_future(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "land_registry_lodged", "event_date": "2099-01-01"},
    )

    assert response.status_code == 422


def test_there_is_no_route_that_edits_or_deletes_a_legal_event(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    event_id = _timeline(legal_client, project_id, active_sale)["events"][0]["id"]
    base = f"{sales_url(project_id)}/legal-events/{event_id}"

    assert legal_client.patch(base, json={"event_date": "2026-03-01"}).status_code in {404, 405}
    assert legal_client.delete(base).status_code in {404, 405}


def test_a_mistake_is_corrected_by_a_reversal_that_keeps_both_records(
    legal_client: TestClient,
    admin_client: TestClient,
    project_id: str,
    active_sale: str,
    released_unit: str,
) -> None:
    record_legal(legal_client, project_id, active_sale, "land_registry_lodged", "2026-02-10")
    before = _timeline(legal_client, project_id, active_sale)
    lodged = next(
        event for event in before["events"] if event["event_type"] == "land_registry_lodged"
    )

    response = legal_client.post(
        f"{sales_url(project_id)}/legal-events/{lodged['id']}/reverse",
        json={"reason": "Lodged against the wrong plot reference"},
    )

    assert response.status_code == 200, response.text
    after = response.json()
    # Both rows survive: the original and the correction that withdraws it.
    assert len(after["events"]) == len(before["events"]) + 1
    assert lodged["id"] not in after["effective_event_ids"]
    assert after["legal_status"] == "fully_signed"
    assert _legal_status(admin_client, project_id, released_unit) == "fully_signed"


def test_a_reversal_needs_a_reason(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    event_id = _timeline(legal_client, project_id, active_sale)["events"][-1]["id"]

    response = legal_client.post(
        f"{sales_url(project_id)}/legal-events/{event_id}/reverse", json={}
    )

    assert response.status_code == 422


def test_a_later_milestone_must_be_reversed_first(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    record_legal(legal_client, project_id, active_sale, "land_registry_lodged", "2026-02-10")
    signed = next(
        event
        for event in _timeline(legal_client, project_id, active_sale)["events"]
        if event["event_type"] == "seller_signed"
    )

    response = legal_client.post(
        f"{sales_url(project_id)}/legal-events/{signed['id']}/reverse",
        json={"reason": "Signature page was unsigned"},
    )

    assert response.status_code == 409
    assert "Reverse the later events first" in response.json()["detail"]


def test_title_transfer_waits_for_the_collection_clearance_the_project_requires(
    legal_client: TestClient,
    sales_ops_client: TestClient,
    collections_client: TestClient,
    finance_client: TestClient,
    project_id: str,
    active_sale: str,
    active_plan: tuple[str, str],
) -> None:
    """The default policy requires collections to be clear before title moves.

    From PR-MVP-07 that clearance is checked against the receivables ledger
    rather than attested, so the gate only opens once the money is actually in.
    """
    for event_type, event_date in (
        ("land_registry_lodged", "2026-02-10"),
        ("registered", "2026-02-20"),
    ):
        record_legal(legal_client, project_id, active_sale, event_type, event_date)

    refused = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "title_transferred", "event_date": "2026-03-01"},
    )
    assert refused.status_code == 409
    assert "collection clearance" in refused.json()["detail"]

    handover = sales_ops_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/handover", json={}
    )
    assert handover.status_code == 201, handover.text
    assert handover.json()["handover"]["id"]
    settle_and_clear_collections(collections_client, finance_client, project_id, active_sale)

    allowed = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "title_transferred", "event_date": "2026-03-01"},
    )
    assert allowed.status_code == 201, allowed.text


def test_a_fee_recorded_on_the_timeline_is_a_legal_fact_not_a_payment(
    legal_client: TestClient, project_id: str, active_sale: str, currency_id: str
) -> None:
    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={
            "event_type": "stamped",
            "event_date": "2026-02-06",
            "fee_amount": "1250.00",
            "currency_id": currency_id,
            "authority_reference": "STAMP-2026-88",
        },
    )

    assert response.status_code == 201, response.text
    stamped = next(event for event in response.json()["events"] if event["event_type"] == "stamped")
    assert stamped["fee_amount"] == "1250.00"
    # No route on this module treats it as collected or paid: it is what the
    # authority charged, recorded where the authority's act is recorded.
    assert "paid" not in stamped


def test_a_fee_without_a_currency_is_refused(
    legal_client: TestClient, project_id: str, active_sale: str
) -> None:
    response = legal_client.post(
        f"{sales_url(project_id)}/contracts/{active_sale}/legal-events",
        json={"event_type": "stamped", "event_date": "2026-02-06", "fee_amount": "1250.00"},
    )

    assert response.status_code == 422
    assert "currency" in response.json()["detail"]


def test_the_legal_timeline_reports_the_next_step_the_register_is_waiting_for(
    sales_ops_client: TestClient, project_id: str, active_sale: str, released_unit: str
) -> None:
    response = sales_ops_client.get(f"{sales_url(project_id)}/register")

    assert response.status_code == 200, response.text
    row = next(item for item in response.json()["rows"] if item["unit_id"] == released_unit)
    assert row["next_legal_step"] == "land_registry_lodged"
    assert row["legal_status"] == "fully_signed"
    assert row["commercial_status"] == "contracted"
