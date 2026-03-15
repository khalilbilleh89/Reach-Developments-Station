"""
Tests for the collections API endpoints.

Validates HTTP behaviour, request/response contracts, and full
receipt + receivables workflows via the REST layer.
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_hierarchy(client: TestClient, proj_code: str = "PRJ-COL-API") -> str:
    """Create a full project hierarchy and return unit_id."""
    project_id = client.post(
        "/api/v1/projects", json={"name": "Col API Project", "code": proj_code}
    ).json()["id"]
    phase_id = client.post(
        "/api/v1/phases",
        json={"project_id": project_id, "name": "Phase 1", "sequence": 1},
    ).json()["id"]
    building_id = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": "BLK-A"},
    ).json()["id"]
    floor_id = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": "FL-01", "sequence_number": 1},
    ).json()["id"]
    unit_id = client.post(
        "/api/v1/units",
        json={
            "floor_id": floor_id,
            "unit_number": "101",
            "unit_type": "studio",
            "internal_area": 100.0,
        },
    ).json()["id"]
    return unit_id


def _create_contract(
    client: TestClient,
    proj_code: str = "PRJ-COL-API",
    contract_price: float = 200_000.0,
    contract_number: str = "CNT-COL-001",
    email: str = "colbuyer@test.com",
) -> str:
    unit_id = _create_hierarchy(client, proj_code)
    buyer_id = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": "Col Buyer", "email": email, "phone": "+9620000001"},
    ).json()["id"]
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-01-01",
            "contract_price": contract_price,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_schedule(
    client: TestClient,
    contract_id: str,
    start_date: str = "2030-01-01",
    number_of_installments: int = 3,
    down_payment_percent: float = 10.0,
) -> list:
    """Create a payment plan template and generate a schedule. Returns schedule items."""
    template_id = client.post(
        "/api/v1/payment-plans/templates",
        json={
            "name": "Col Test Plan",
            "down_payment_percent": down_payment_percent,
            "number_of_installments": number_of_installments,
            "installment_frequency": "monthly",
        },
    ).json()["id"]

    resp = client.post(
        "/api/v1/payment-plans/generate",
        json={
            "contract_id": contract_id,
            "template_id": template_id,
            "start_date": start_date,
        },
    )
    assert resp.status_code == 201
    return resp.json()["items"]


# ---------------------------------------------------------------------------
# POST /api/v1/collections/receipts
# ---------------------------------------------------------------------------


def test_record_receipt_returns_201(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-REC1", email="ca1@test.com")
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": first_line["due_amount"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["payment_schedule_id"] == first_line["id"]
    assert data["status"] == "recorded"
    assert "id" in data
    assert "created_at" in data


def test_record_receipt_with_optional_fields(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-OPT", email="caopt@test.com")
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": first_line["due_amount"],
            "payment_method": "bank_transfer",
            "reference_number": "REF-2026-001",
            "notes": "Test note",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["payment_method"] == "bank_transfer"
    assert data["reference_number"] == "REF-2026-001"


def test_record_receipt_invalid_contract_returns_404(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-IC", email="caic@test.com")
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": "no-such-contract",
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": 100.0,
        },
    )
    assert resp.status_code == 404


def test_record_receipt_invalid_schedule_returns_404(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-IS", email="cais@test.com")
    _create_schedule(client, contract_id)

    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": "no-such-schedule",
            "receipt_date": "2026-01-10",
            "amount_received": 100.0,
        },
    )
    assert resp.status_code == 404


def test_record_receipt_cross_contract_returns_422(client: TestClient):
    """Schedule line from contract A cannot be settled via contract B."""
    contract_a = _create_contract(
        client, "PRJ-CA-CRA", email="cra@test.com", contract_number="CNT-CRA-001"
    )
    contract_b = _create_contract(
        client, "PRJ-CA-CRB", email="crb@test.com", contract_number="CNT-CRB-001"
    )
    schedule_a = _create_schedule(client, contract_a)
    _create_schedule(client, contract_b)

    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_b,
            "payment_schedule_id": schedule_a[0]["id"],
            "receipt_date": "2026-01-10",
            "amount_received": 100.0,
        },
    )
    assert resp.status_code == 422


def test_record_receipt_overpayment_returns_422(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-OVR", email="caovr@test.com")
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    # First receipt settles the line
    client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": first_line["due_amount"],
        },
    )

    # Second receipt would overpay
    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-12",
            "amount_received": 1.0,
        },
    )
    assert resp.status_code == 422


def test_record_receipt_zero_amount_returns_422(client: TestClient):
    """amount_received must be > 0."""
    contract_id = _create_contract(client, "PRJ-CA-ZERO", email="cazero@test.com")
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    resp = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": 0.0,
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/collections/receipts/{receipt_id}
# ---------------------------------------------------------------------------


def test_get_receipt_by_id(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-GR", email="cagr@test.com")
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    created = client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": first_line["due_amount"],
        },
    ).json()

    resp = client.get(f"/api/v1/collections/receipts/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_receipt_not_found(client: TestClient):
    resp = client.get("/api/v1/collections/receipts/no-such-receipt")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/collections/contracts/{contract_id}/receipts
# ---------------------------------------------------------------------------


def test_list_receipts_for_contract(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-LR", email="calr@test.com")
    schedule = _create_schedule(client, contract_id)

    for line in schedule[:2]:
        client.post(
            "/api/v1/collections/receipts",
            json={
                "contract_id": contract_id,
                "payment_schedule_id": line["id"],
                "receipt_date": "2026-01-10",
                "amount_received": line["due_amount"],
            },
        )

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receipts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert data["total"] == 2
    assert data["total_received"] == pytest.approx(
        sum(line["due_amount"] for line in schedule[:2])
    )


def test_list_receipts_invalid_contract_returns_404(client: TestClient):
    resp = client.get("/api/v1/collections/contracts/no-such-contract/receipts")
    assert resp.status_code == 404


def test_list_receipts_empty_for_new_contract(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-EMPTY", email="caempty@test.com")
    _create_schedule(client, contract_id)

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receipts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_received"] == 0.0


# ---------------------------------------------------------------------------
# GET /api/v1/collections/contracts/{contract_id}/receivables
# ---------------------------------------------------------------------------


def test_get_receivables_returns_correct_structure(client: TestClient):
    contract_id = _create_contract(client, "PRJ-CA-RCV", email="carcv@test.com")
    _create_schedule(client, contract_id)

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_id"] == contract_id
    assert "items" in data
    assert "total_due" in data
    assert "total_received" in data
    assert "total_outstanding" in data
    for item in data["items"]:
        assert "schedule_id" in item
        assert "due_date" in item
        assert "due_amount" in item
        assert "total_received" in item
        assert "outstanding_amount" in item
        assert "receivable_status" in item


def test_get_receivables_pending_status(client: TestClient):
    """Lines with future due dates and no receipts should be pending."""
    contract_id = _create_contract(client, "PRJ-CA-PEND", email="capend@test.com")
    _create_schedule(client, contract_id, start_date="2030-01-01")

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["receivable_status"] == "pending"
        assert item["total_received"] == 0.0
        assert item["outstanding_amount"] == pytest.approx(item["due_amount"])


def test_get_receivables_after_full_payment(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-CA-FPAY", email="cafpay@test.com", contract_price=100_000.0
    )
    schedule = _create_schedule(client, contract_id)
    first_line = schedule[0]

    client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": first_line["due_amount"],
        },
    )

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    data = resp.json()
    first = data["items"][0]
    assert first["receivable_status"] == "paid"
    assert first["outstanding_amount"] == pytest.approx(0.0)


def test_get_receivables_partial_payment(client: TestClient):
    contract_id = _create_contract(
        client, "PRJ-CA-PPAY", email="cappay@test.com", contract_price=100_000.0
    )
    schedule = _create_schedule(client, contract_id, start_date="2030-01-01")
    first_line = schedule[0]
    partial = round(first_line["due_amount"] / 2, 2)

    client.post(
        "/api/v1/collections/receipts",
        json={
            "contract_id": contract_id,
            "payment_schedule_id": first_line["id"],
            "receipt_date": "2026-01-10",
            "amount_received": partial,
        },
    )

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    first = resp.json()["items"][0]
    assert first["receivable_status"] == "partially_paid"
    assert first["total_received"] == pytest.approx(partial)
    assert first["outstanding_amount"] == pytest.approx(
        first_line["due_amount"] - partial
    )


def test_get_receivables_overdue(client: TestClient):
    """Unpaid lines with past due dates must be overdue."""
    contract_id = _create_contract(client, "PRJ-CA-OVRD", email="caovrd@test.com")
    past_date = (date.today() - timedelta(days=30)).isoformat()
    _create_schedule(client, contract_id, start_date=past_date)

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    first = resp.json()["items"][0]
    assert first["receivable_status"] == "overdue"


def test_get_receivables_invalid_contract_returns_404(client: TestClient):
    resp = client.get("/api/v1/collections/contracts/no-such-contract/receivables")
    assert resp.status_code == 404


def test_get_receivables_totals_correct(client: TestClient):
    """Contract-level totals must match sums of line-level values."""
    contract_id = _create_contract(
        client, "PRJ-CA-TOT", email="catot@test.com", contract_price=300_000.0
    )
    schedule = _create_schedule(client, contract_id, number_of_installments=3)

    # Settle first two lines fully
    for line in schedule[:2]:
        client.post(
            "/api/v1/collections/receipts",
            json={
                "contract_id": contract_id,
                "payment_schedule_id": line["id"],
                "receipt_date": "2026-01-10",
                "amount_received": line["due_amount"],
            },
        )

    resp = client.get(f"/api/v1/collections/contracts/{contract_id}/receivables")
    assert resp.status_code == 200
    data = resp.json()

    assert abs(data["total_due"] - 300_000.0) < 0.02
    expected_received = sum(line["due_amount"] for line in schedule[:2])
    assert abs(data["total_received"] - expected_received) < 0.02
    assert (
        abs(data["total_outstanding"] - (data["total_due"] - data["total_received"]))
        < 0.01
    )
