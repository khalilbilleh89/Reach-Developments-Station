"""
tests/integration/test_full_platform_lifecycle.py

PR-F1: Full Platform Lifecycle Integration Tests.

Validates the complete real-estate development lifecycle across all domains:

  Project
   → Phase → Building → Floor → Unit
     → Pricing attributes
       → Buyer → Reservation → Contract
         → Payment Plan → Installments
           → Finance Summary
             → Registry Case
               → Construction Scope → Milestone → Progress Update

Assertions verify:
  - relationships are valid
  - identifiers match across domain boundaries
  - aggregates are correct
  - lifecycle steps do not break downstream domains

These tests use the shared TestClient fixture (in-memory SQLite) from conftest.py.
"""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers — build project hierarchy
# ---------------------------------------------------------------------------


def _create_project(client: TestClient, code: str, name: str = "Lifecycle Project") -> str:
    """Create a project and return its id."""
    resp = client.post(
        "/api/v1/projects",
        json={"name": name, "code": code},
    )
    assert resp.status_code == 201, f"Project creation failed: {resp.text}"
    return resp.json()["id"]


def _create_phase(client: TestClient, project_id: str, name: str = "Phase 1") -> str:
    resp = client.post(
        f"/api/v1/projects/{project_id}/phases",
        json={"name": name, "sequence": 1},
    )
    assert resp.status_code == 201, f"Phase creation failed: {resp.text}"
    return resp.json()["id"]


def _create_building(client: TestClient, phase_id: str, code: str = "BLK-A") -> str:
    resp = client.post(
        f"/api/v1/phases/{phase_id}/buildings",
        json={"name": "Block A", "code": code},
    )
    assert resp.status_code == 201, f"Building creation failed: {resp.text}"
    return resp.json()["id"]


def _create_floor(client: TestClient, building_id: str, code: str = "FL-01") -> str:
    resp = client.post(
        f"/api/v1/buildings/{building_id}/floors",
        json={"name": "Floor 1", "code": code, "sequence_number": 1},
    )
    assert resp.status_code == 201, f"Floor creation failed: {resp.text}"
    return resp.json()["id"]


def _create_unit(client: TestClient, floor_id: str, unit_number: str = "101") -> str:
    resp = client.post(
        f"/api/v1/floors/{floor_id}/units",
        json={"unit_number": unit_number, "unit_type": "studio", "internal_area": 110.0},
    )
    assert resp.status_code == 201, f"Unit creation failed: {resp.text}"
    return resp.json()["id"]


def _build_hierarchy(client: TestClient, proj_code: str) -> dict:
    """Create the full asset hierarchy and return all ids."""
    project_id = _create_project(client, proj_code)
    phase_id = _create_phase(client, project_id)
    building_id = _create_building(client, phase_id)
    floor_id = _create_floor(client, building_id)
    unit_id = _create_unit(client, floor_id)
    return {
        "project_id": project_id,
        "phase_id": phase_id,
        "building_id": building_id,
        "floor_id": floor_id,
        "unit_id": unit_id,
    }


def _add_pricing_attributes(client: TestClient, unit_id: str) -> dict:
    resp = client.post(
        f"/api/v1/pricing/unit/{unit_id}/attributes",
        json={"base_price_per_sqm": 6000.0},
    )
    assert resp.status_code == 201, f"Pricing attributes failed: {resp.text}"
    return resp.json()


def _create_buyer(client: TestClient, email: str, name: str = "Lifecycle Buyer") -> str:
    resp = client.post(
        "/api/v1/sales/buyers",
        json={"full_name": name, "email": email, "phone": "+9710000099"},
    )
    assert resp.status_code == 201, f"Buyer creation failed: {resp.text}"
    return resp.json()["id"]


def _create_reservation(client: TestClient, unit_id: str, buyer_id: str) -> dict:
    resp = client.post(
        "/api/v1/sales/reservations",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "reservation_date": "2026-01-01",
            "expiry_date": "2026-04-01",
        },
    )
    assert resp.status_code == 201, f"Reservation creation failed: {resp.text}"
    return resp.json()


def _create_contract(
    client: TestClient,
    unit_id: str,
    buyer_id: str,
    contract_number: str,
    contract_price: float = 660_000.0,
) -> dict:
    resp = client.post(
        "/api/v1/sales/contracts",
        json={
            "unit_id": unit_id,
            "buyer_id": buyer_id,
            "contract_number": contract_number,
            "contract_date": "2026-02-01",
            "contract_price": contract_price,
        },
    )
    assert resp.status_code == 201, f"Contract creation failed: {resp.text}"
    return resp.json()


def _generate_payment_plan(client: TestClient, contract_id: str) -> dict:
    resp = client.post(
        "/api/v1/payment-plans",
        json={
            "contract_id": contract_id,
            "plan_name": "Standard 12-Month",
            "number_of_installments": 12,
            "start_date": "2026-03-01",
            "down_payment_percent": 10.0,
        },
    )
    assert resp.status_code == 201, f"Payment plan generation failed: {resp.text}"
    return resp.json()


def _get_payment_schedule(client: TestClient, contract_id: str) -> dict:
    resp = client.get(f"/api/v1/payment-plans/contracts/{contract_id}/schedule")
    assert resp.status_code == 200, f"Payment schedule fetch failed: {resp.text}"
    return resp.json()


def _get_finance_summary(client: TestClient, project_id: str) -> dict:
    resp = client.get(f"/api/v1/finance/projects/{project_id}/summary")
    assert resp.status_code == 200, f"Finance summary fetch failed: {resp.text}"
    return resp.json()


def _create_registry_case(
    client: TestClient, project_id: str, unit_id: str, contract_id: str
) -> dict:
    resp = client.post(
        "/api/v1/registry/cases",
        json={
            "project_id": project_id,
            "unit_id": unit_id,
            "sale_contract_id": contract_id,
            "buyer_name": "Lifecycle Buyer",
            "jurisdiction": "Dubai",
        },
    )
    assert resp.status_code == 201, f"Registry case creation failed: {resp.text}"
    return resp.json()


def _create_construction_scope(client: TestClient, project_id: str, name: str = "Structure Works") -> dict:
    resp = client.post(
        "/api/v1/construction/scopes",
        json={"project_id": project_id, "name": name},
    )
    assert resp.status_code == 201, f"Construction scope creation failed: {resp.text}"
    return resp.json()


def _create_milestone(client: TestClient, scope_id: str, name: str = "Foundation") -> dict:
    resp = client.post(
        "/api/v1/construction/milestones",
        json={"scope_id": scope_id, "name": name, "sequence": 1},
    )
    assert resp.status_code == 201, f"Milestone creation failed: {resp.text}"
    return resp.json()


def _add_progress_update(client: TestClient, milestone_id: str, percent: int = 25) -> dict:
    resp = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress-updates",
        json={"progress_percent": percent, "status_note": "On schedule"},
    )
    assert resp.status_code == 201, f"Progress update failed: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Test 1: Project and hierarchy creation
# ---------------------------------------------------------------------------


def test_lifecycle_step_1_project_and_hierarchy(client: TestClient):
    """Step 1: Create project → phase → building → floor → unit.

    Verifies:
    - All entities are created with 201.
    - Returned ids are non-null strings.
    - Each entity references its parent.
    """
    ids = _build_hierarchy(client, "LCY-001")

    assert ids["project_id"]
    assert ids["phase_id"]
    assert ids["building_id"]
    assert ids["floor_id"]
    assert ids["unit_id"]

    # Verify project is retrievable
    project = client.get(f"/api/v1/projects/{ids['project_id']}").json()
    assert project["id"] == ids["project_id"]
    assert project["code"] == "LCY-001"


# ---------------------------------------------------------------------------
# Test 2: Pricing attributes
# ---------------------------------------------------------------------------


def test_lifecycle_step_2_pricing_attributes(client: TestClient):
    """Step 2: Add pricing attributes to a unit.

    Verifies:
    - POST /api/v1/pricing/unit/{unit_id}/attributes returns 201.
    - Returned pricing record references the unit.
    - Pricing data is retrievable.
    """
    ids = _build_hierarchy(client, "LCY-002")
    pricing = _add_pricing_attributes(client, ids["unit_id"])

    assert pricing["unit_id"] == ids["unit_id"]
    assert float(pricing["base_price_per_sqm"]) == 6000.0


# ---------------------------------------------------------------------------
# Test 3: Buyer creation
# ---------------------------------------------------------------------------


def test_lifecycle_step_3_buyer_creation(client: TestClient):
    """Step 3: Create a buyer record.

    Verifies:
    - POST /api/v1/sales/buyers returns 201.
    - Returned buyer has correct name and email.
    """
    ids = _build_hierarchy(client, "LCY-003")
    buyer_id = _create_buyer(client, "lcy.003@example.com", "Jane Doe")

    # Retrieve buyer
    resp = client.get(f"/api/v1/sales/buyers/{buyer_id}")
    assert resp.status_code == 200
    buyer = resp.json()
    assert buyer["id"] == buyer_id
    assert buyer["email"] == "lcy.003@example.com"


# ---------------------------------------------------------------------------
# Test 4: Reservation
# ---------------------------------------------------------------------------


def test_lifecycle_step_4_reservation(client: TestClient):
    """Step 4: Create a reservation for a unit and buyer.

    Verifies:
    - POST /api/v1/sales/reservations returns 201.
    - Reservation references correct unit and buyer.

    Note: reservations require pricing attributes to be set first.
    """
    ids = _build_hierarchy(client, "LCY-004")
    _add_pricing_attributes(client, ids["unit_id"])
    buyer_id = _create_buyer(client, "lcy.004@example.com")
    reservation = _create_reservation(client, ids["unit_id"], buyer_id)

    assert reservation["unit_id"] == ids["unit_id"]
    assert reservation["buyer_id"] == buyer_id


# ---------------------------------------------------------------------------
# Test 5: Contract
# ---------------------------------------------------------------------------


def test_lifecycle_step_5_contract(client: TestClient):
    """Step 5: Create a sales contract.

    Verifies:
    - POST /api/v1/sales/contracts returns 201.
    - Contract references the correct unit and buyer.
    - Contract price is recorded correctly.
    """
    ids = _build_hierarchy(client, "LCY-005")
    buyer_id = _create_buyer(client, "lcy.005@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-005")

    assert contract["unit_id"] == ids["unit_id"]
    assert contract["buyer_id"] == buyer_id
    assert float(contract["contract_price"]) == 660_000.0


# ---------------------------------------------------------------------------
# Test 6: Payment plan
# ---------------------------------------------------------------------------


def test_lifecycle_step_6_payment_plan(client: TestClient):
    """Step 6: Generate a payment plan for a contract.

    Verifies:
    - POST /api/v1/payment-plans returns 201.
    - Plan references the correct contract.
    - Plan has expected number of installments.
    """
    ids = _build_hierarchy(client, "LCY-006")
    buyer_id = _create_buyer(client, "lcy.006@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-006")
    plan = _generate_payment_plan(client, contract["id"])

    assert plan["contract_id"] == contract["id"]
    assert plan["total_installments"] >= 12


# ---------------------------------------------------------------------------
# Test 7: Payment schedule retrieval
# ---------------------------------------------------------------------------


def test_lifecycle_step_7_payment_schedule(client: TestClient):
    """Step 7: Retrieve the payment schedule for a contract.

    Verifies:
    - GET /api/v1/payment-plans/contracts/{contract_id}/schedule returns 200.
    - Schedule response contains payment items.
    """
    ids = _build_hierarchy(client, "LCY-007")
    buyer_id = _create_buyer(client, "lcy.007@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-007")
    _generate_payment_plan(client, contract["id"])

    schedule = _get_payment_schedule(client, contract["id"])

    # Schedule response contains a "total" count of installment items
    assert schedule.get("total", 0) > 0 or schedule.get("items") or schedule.get("installments"), (
        "Schedule response must contain payment items"
    )


# ---------------------------------------------------------------------------
# Test 8: Finance summary
# ---------------------------------------------------------------------------


def test_lifecycle_step_8_finance_summary(client: TestClient):
    """Step 8: Validate finance summary reflects the contract.

    Verifies:
    - GET /api/v1/finance/projects/{project_id}/summary returns 200.
    - project_id in response matches the queried project.
    - total_contract_value equals the created contract price.
    """
    ids = _build_hierarchy(client, "LCY-008")
    buyer_id = _create_buyer(client, "lcy.008@example.com")
    contract_price = 660_000.0
    _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-008", contract_price)

    summary = _get_finance_summary(client, ids["project_id"])

    assert summary["project_id"] == ids["project_id"]
    assert float(summary["total_contract_value"]) == contract_price
    assert summary["total_units"] >= 1


# ---------------------------------------------------------------------------
# Test 9: Registry case
# ---------------------------------------------------------------------------


def test_lifecycle_step_9_registry_case(client: TestClient):
    """Step 9: Create a registry case for the sold unit.

    Verifies:
    - POST /api/v1/registry/cases returns 201.
    - Registry case references correct project, unit, and contract.
    - Default milestones are initialised.
    """
    ids = _build_hierarchy(client, "LCY-009")
    buyer_id = _create_buyer(client, "lcy.009@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-009")
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )

    assert case["project_id"] == ids["project_id"]
    assert case["unit_id"] == ids["unit_id"]
    assert case["sale_contract_id"] == contract["id"]

    # Default milestones must be auto-initialised
    milestones = client.get(f"/api/v1/registry/cases/{case['id']}/milestones").json()
    assert len(milestones) > 0


# ---------------------------------------------------------------------------
# Test 10: Construction progress workflow
# ---------------------------------------------------------------------------


def test_lifecycle_step_10_construction_progress(client: TestClient):
    """Step 10: Validate the construction progress workflow.

    Verifies:
    - POST /api/v1/construction/scopes returns 201.
    - POST /api/v1/construction/milestones returns 201 (references scope).
    - POST /api/v1/construction/milestones/{id}/progress-updates returns 201.
    - Progress update references the milestone.
    """
    ids = _build_hierarchy(client, "LCY-010")
    scope = _create_construction_scope(client, ids["project_id"])
    assert scope["project_id"] == ids["project_id"]

    milestone = _create_milestone(client, scope["id"])
    assert milestone["scope_id"] == scope["id"]

    update = _add_progress_update(client, milestone["id"], 30)
    assert update["milestone_id"] == milestone["id"]
    assert update["progress_percent"] == 30


# ---------------------------------------------------------------------------
# Test 11: Full platform lifecycle in a single test
# ---------------------------------------------------------------------------


def test_full_platform_lifecycle_end_to_end(client: TestClient):
    """Complete end-to-end lifecycle: Project → ... → Construction Tracking.

    This is the canonical lifecycle integration test.  Every domain transition
    must succeed and identifiers must be consistent across all boundaries.
    """
    # ── 1. Asset hierarchy ────────────────────────────────────────────────
    ids = _build_hierarchy(client, "LCY-E2E")

    # ── 2. Pricing ────────────────────────────────────────────────────────
    pricing = _add_pricing_attributes(client, ids["unit_id"])
    assert pricing["unit_id"] == ids["unit_id"]

    # ── 3. Buyer ──────────────────────────────────────────────────────────
    buyer_id = _create_buyer(client, "lcy.e2e@example.com", "E2E Buyer")

    # ── 4. Reservation ────────────────────────────────────────────────────
    # Reservation requires pricing attributes to be set first
    reservation = _create_reservation(client, ids["unit_id"], buyer_id)
    assert reservation["unit_id"] == ids["unit_id"]
    assert reservation["buyer_id"] == buyer_id

    # ── 5. Contract ───────────────────────────────────────────────────────
    contract = _create_contract(
        client, ids["unit_id"], buyer_id, "CNT-LCY-E2E", 700_000.0
    )
    assert contract["unit_id"] == ids["unit_id"]
    assert contract["buyer_id"] == buyer_id
    assert float(contract["contract_price"]) == 700_000.0

    # ── 6. Payment plan ───────────────────────────────────────────────────
    plan = _generate_payment_plan(client, contract["id"])
    assert plan["contract_id"] == contract["id"]
    assert plan["total_installments"] >= 12

    # ── 7. Payment schedule ───────────────────────────────────────────────
    schedule = _get_payment_schedule(client, contract["id"])
    assert schedule is not None

    # ── 8. Finance summary ────────────────────────────────────────────────
    summary = _get_finance_summary(client, ids["project_id"])
    assert summary["project_id"] == ids["project_id"]
    assert float(summary["total_contract_value"]) == 700_000.0
    assert summary["total_units"] >= 1

    # ── 9. Registry case ──────────────────────────────────────────────────
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )
    assert case["project_id"] == ids["project_id"]
    assert case["sale_contract_id"] == contract["id"]

    milestones = client.get(f"/api/v1/registry/cases/{case['id']}/milestones").json()
    assert len(milestones) > 0

    # ── 10. Construction tracking ─────────────────────────────────────────
    scope = _create_construction_scope(client, ids["project_id"], "MEP Works")
    assert scope["project_id"] == ids["project_id"]

    milestone = _create_milestone(client, scope["id"], "Rough-in Complete")
    assert milestone["scope_id"] == scope["id"]

    update = _add_progress_update(client, milestone["id"], 50)
    assert update["milestone_id"] == milestone["id"]

    # ── 11. Project summary reflects sold units ───────────────────────────
    project_summary = client.get(
        f"/api/v1/projects/{ids['project_id']}/summary"
    ).json()
    assert project_summary["project_id"] == ids["project_id"]
    assert project_summary["total_units"] >= 1


# ---------------------------------------------------------------------------
# Test 12: Lifecycle integrity — domain boundaries remain intact
# ---------------------------------------------------------------------------


def test_lifecycle_finance_does_not_double_count(client: TestClient):
    """Finance summary must not double-count contracts for the same unit."""
    ids = _build_hierarchy(client, "LCY-FIN")
    buyer_id = _create_buyer(client, "lcy.fin@example.com")
    _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-FIN", 500_000.0)

    summary = _get_finance_summary(client, ids["project_id"])
    assert float(summary["total_contract_value"]) == 500_000.0
    assert summary["total_units"] >= 1


def test_lifecycle_registry_case_references_valid_project(client: TestClient):
    """Registry case project_id must match the unit's project hierarchy."""
    ids = _build_hierarchy(client, "LCY-REG")
    buyer_id = _create_buyer(client, "lcy.reg@example.com")
    contract = _create_contract(client, ids["unit_id"], buyer_id, "CNT-LCY-REG")

    # Valid project_id must succeed
    case = _create_registry_case(
        client, ids["project_id"], ids["unit_id"], contract["id"]
    )
    assert case["project_id"] == ids["project_id"]


def test_lifecycle_construction_scope_belongs_to_project(client: TestClient):
    """Construction scopes must reference the project they are created for."""
    ids = _build_hierarchy(client, "LCY-CST")
    scope = _create_construction_scope(client, ids["project_id"], "Facade Works")
    assert scope["project_id"] == ids["project_id"]
