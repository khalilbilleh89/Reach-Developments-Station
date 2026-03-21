"""
Tests for the PR-14 Pricing Override & Premium Rules Engine.

Validates:
  - premium calculations match deterministic rules (premium_rules.py)
  - override thresholds enforced (override_rules.py)
  - unauthorized overrides rejected
  - premium breakdown API accuracy
  - approved pricing cannot be overridden
  - override metadata stored correctly
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.pricing.override_rules import (
    OVERRIDE_THRESHOLDS,
    assert_override_allowed,
    calculate_override_percent,
    required_approver_role,
)
from app.modules.pricing.premium_rules import (
    PremiumBreakdownResult,
    calculate_premium_breakdown,
)
from app.modules.pricing.schemas import (
    PricingOverrideRequest,
    UnitPricingAttributesCreate,
)
from app.modules.pricing.service import PricingService, UnitPricingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(db: Session, project_code: str = "PRJ-OVR") -> str:
    """Create a full project hierarchy and return a unit ID."""
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.projects.models import Project
    from app.modules.units.models import Unit

    project = Project(name=f"Override Test Project {project_code}", code=project_code)
    db.add(project)
    db.flush()

    phase = Phase(project_id=project.id, name="Phase 1", sequence=1)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code="BLK-A")
    db.add(building)
    db.flush()

    floor = Floor(
        building_id=building.id, name="Floor 1", code="FL-01", sequence_number=1
    )
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number="101",
        unit_type="studio",
        internal_area=100.0,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit.id


def _create_hierarchy(client: TestClient, proj_code: str) -> tuple[str, str]:
    """Create a full hierarchy via API and return (project_id, unit_id)."""
    project_id = client.post(
        "/api/v1/projects",
        json={"name": f"Override Project {proj_code}", "code": proj_code},
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
    return project_id, unit_id


_VALID_ATTRS = UnitPricingAttributesCreate(
    base_price_per_sqm=5000.0,
    floor_premium=10_000.0,
    view_premium=15_000.0,
    corner_premium=5_000.0,
    size_adjustment=2_000.0,
    custom_adjustment=-1_000.0,
)

_VALID_ATTRS_PAYLOAD = {
    "base_price_per_sqm": 5000.0,
    "floor_premium": 10_000.0,
    "view_premium": 15_000.0,
    "corner_premium": 5_000.0,
    "size_adjustment": 2_000.0,
    "custom_adjustment": -1_000.0,
}


# ===========================================================================
# Unit tests — premium_rules.calculate_premium_breakdown
# ===========================================================================


class TestPremiumRules:
    def test_returns_frozen_dataclass(self):
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=100.0,
            base_price_per_sqm=5000.0,
        )
        assert isinstance(result, PremiumBreakdownResult)

    def test_base_unit_price_formula(self):
        """base_unit_price = base_price_per_sqm * unit_area."""
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=80.0,
            base_price_per_sqm=5000.0,
        )
        assert result.base_unit_price == pytest.approx(400_000.0)

    def test_premium_total_sum(self):
        """premium_total = floor + view + corner + size + custom."""
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=100.0,
            base_price_per_sqm=5000.0,
            floor_premium=10_000.0,
            view_premium=15_000.0,
            corner_premium=5_000.0,
            size_adjustment=2_000.0,
            custom_adjustment=-1_000.0,
        )
        assert result.premium_total == pytest.approx(31_000.0)

    def test_final_unit_price(self):
        """final_unit_price = base_unit_price + premium_total."""
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=100.0,
            base_price_per_sqm=5000.0,
            floor_premium=10_000.0,
            view_premium=15_000.0,
            corner_premium=5_000.0,
            size_adjustment=2_000.0,
            custom_adjustment=-1_000.0,
        )
        # base = 500_000; premium = 31_000; final = 531_000
        assert result.final_unit_price == pytest.approx(531_000.0)

    def test_zero_premiums_gives_base_only(self):
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=50.0,
            base_price_per_sqm=4000.0,
        )
        assert result.premium_total == pytest.approx(0.0)
        assert result.final_unit_price == pytest.approx(200_000.0)

    def test_negative_custom_adjustment_reduces_total(self):
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=100.0,
            base_price_per_sqm=5000.0,
            custom_adjustment=-50_000.0,
        )
        assert result.premium_total == pytest.approx(-50_000.0)
        assert result.final_unit_price == pytest.approx(450_000.0)

    def test_unit_id_propagated(self):
        result = calculate_premium_breakdown(
            unit_id="test-unit-42",
            unit_area=100.0,
            base_price_per_sqm=1000.0,
        )
        assert result.unit_id == "test-unit-42"

    def test_individual_components_stored(self):
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=100.0,
            base_price_per_sqm=5000.0,
            floor_premium=10_000.0,
            view_premium=15_000.0,
            corner_premium=5_000.0,
            size_adjustment=2_000.0,
            custom_adjustment=-1_000.0,
        )
        assert result.floor_premium == pytest.approx(10_000.0)
        assert result.view_premium == pytest.approx(15_000.0)
        assert result.corner_premium == pytest.approx(5_000.0)
        assert result.size_adjustment == pytest.approx(2_000.0)
        assert result.custom_adjustment == pytest.approx(-1_000.0)

    def test_result_is_immutable(self):
        """PremiumBreakdownResult is a frozen dataclass — mutation must raise."""
        result = calculate_premium_breakdown(
            unit_id="u1",
            unit_area=100.0,
            base_price_per_sqm=5000.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            result.floor_premium = 99_999.0  # type: ignore[misc]


# ===========================================================================
# Unit tests — override_rules
# ===========================================================================


class TestOverridePercent:
    def test_typical_percentage(self):
        pct = calculate_override_percent(10_000.0, 500_000.0)
        assert pct == pytest.approx(2.0)

    def test_zero_base_price_returns_zero(self):
        pct = calculate_override_percent(10_000.0, 0.0)
        assert pct == pytest.approx(0.0)

    def test_negative_override_uses_absolute(self):
        pct = calculate_override_percent(-25_000.0, 500_000.0)
        assert pct == pytest.approx(5.0)

    def test_large_override_percent(self):
        pct = calculate_override_percent(50_000.0, 500_000.0)
        assert pct == pytest.approx(10.0)


class TestRequiredApproverRole:
    def test_within_sales_manager_threshold(self):
        assert required_approver_role(1.0) == "sales_manager"

    def test_at_sales_manager_limit(self):
        assert required_approver_role(2.0) == "sales_manager"

    def test_above_sales_manager_requires_director(self):
        assert required_approver_role(3.0) == "development_director"

    def test_at_director_limit(self):
        assert required_approver_role(5.0) == "development_director"

    def test_above_director_requires_ceo(self):
        assert required_approver_role(5.1) == "ceo"

    def test_large_override_requires_ceo(self):
        assert required_approver_role(100.0) == "ceo"


class TestAssertOverrideAllowed:
    def test_sales_manager_within_threshold_passes(self):
        assert_override_allowed("sales_manager", 1.5)  # no exception

    def test_sales_manager_at_threshold_passes(self):
        assert_override_allowed("sales_manager", 2.0)

    def test_sales_manager_above_threshold_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            assert_override_allowed("sales_manager", 2.1)
        assert exc_info.value.status_code == 422
        assert "Development Director" in exc_info.value.detail

    def test_development_director_within_threshold_passes(self):
        assert_override_allowed("development_director", 4.9)

    def test_development_director_at_threshold_passes(self):
        assert_override_allowed("development_director", 5.0)

    def test_development_director_above_threshold_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            assert_override_allowed("development_director", 5.1)
        assert exc_info.value.status_code == 422
        assert "CEO" in exc_info.value.detail

    def test_ceo_has_unlimited_authority(self):
        assert_override_allowed("ceo", 99.9)  # no exception

    def test_unknown_role_raises(self):
        with pytest.raises(HTTPException) as exc_info:
            assert_override_allowed("unknown_role", 1.0)
        assert exc_info.value.status_code == 422
        assert "Unknown role" in exc_info.value.detail

    def test_zero_percent_always_passes(self):
        for role in ("sales_manager", "development_director", "ceo"):
            assert_override_allowed(role, 0.0)  # no exception


# ===========================================================================
# Service-layer tests — PricingService.get_premium_breakdown
# ===========================================================================


class TestGetPremiumBreakdown:
    def test_returns_breakdown_with_engine_data(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-PBD1")
        pricing_svc = PricingService(db_session)
        unit_pricing_svc = UnitPricingService(db_session)

        pricing_svc.set_pricing_attributes(unit_id, _VALID_ATTRS)

        from app.modules.pricing.schemas import UnitPricingCreate

        pricing = unit_pricing_svc.create_pricing(
            unit_id,
            UnitPricingCreate(base_price=500_000.0),
        )

        breakdown = pricing_svc.get_premium_breakdown(pricing.id)
        assert breakdown.pricing_id == pricing.id
        assert breakdown.unit_id == unit_id
        assert breakdown.has_engine_breakdown is True
        assert breakdown.floor_premium == pytest.approx(10_000.0)
        assert breakdown.view_premium == pytest.approx(15_000.0)
        assert breakdown.corner_premium == pytest.approx(5_000.0)
        assert breakdown.size_adjustment == pytest.approx(2_000.0)
        assert breakdown.custom_adjustment == pytest.approx(-1_000.0)
        assert breakdown.premium_total == pytest.approx(31_000.0)
        # base = 5000 * 100 = 500_000; final engine = 531_000
        assert breakdown.engine_final_unit_price == pytest.approx(531_000.0)
        assert breakdown.engine_base_unit_price == pytest.approx(500_000.0)

    def test_returns_breakdown_without_engine_data(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-PBD2")
        pricing_svc = PricingService(db_session)
        unit_pricing_svc = UnitPricingService(db_session)

        from app.modules.pricing.schemas import UnitPricingCreate

        pricing = unit_pricing_svc.create_pricing(
            unit_id,
            UnitPricingCreate(base_price=500_000.0),
        )

        breakdown = pricing_svc.get_premium_breakdown(pricing.id)
        assert breakdown.has_engine_breakdown is False
        assert breakdown.floor_premium is None
        assert breakdown.premium_total is None
        assert breakdown.engine_final_unit_price is None
        # Formal record values still present.
        assert breakdown.base_price == pytest.approx(500_000.0)

    def test_raises_404_for_unknown_pricing_id(self, db_session: Session):
        pricing_svc = PricingService(db_session)
        with pytest.raises(HTTPException) as exc_info:
            pricing_svc.get_premium_breakdown("no-such-id")
        assert exc_info.value.status_code == 404


# ===========================================================================
# Service-layer tests — UnitPricingService.apply_pricing_override
# ===========================================================================


class TestApplyPricingOverride:
    def _make_pricing(
        self,
        db: Session,
        unit_id: str,
        base_price: float = 500_000.0,
    ):
        from app.modules.pricing.schemas import UnitPricingCreate

        svc = UnitPricingService(db)
        return svc.create_pricing(unit_id, UnitPricingCreate(base_price=base_price))

    def test_sales_manager_within_threshold_succeeds(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV1")
        pricing = self._make_pricing(db_session, unit_id, 500_000.0)
        svc = UnitPricingService(db_session)

        req = PricingOverrideRequest(
            override_amount=5_000.0,  # 1% → within sales_manager limit
            override_reason="Client negotiation",
            requested_by="alice",
            role="sales_manager",
        )
        result = svc.apply_pricing_override(pricing.id, req)
        assert result.manual_adjustment == pytest.approx(5_000.0)
        assert result.final_price == pytest.approx(505_000.0)
        assert result.override_reason == "Client negotiation"
        assert result.override_requested_by == "alice"
        assert result.override_approved_by == "alice"

    def test_sales_manager_above_threshold_raises(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV2")
        pricing = self._make_pricing(db_session, unit_id, 500_000.0)
        svc = UnitPricingService(db_session)

        req = PricingOverrideRequest(
            override_amount=15_000.0,  # 3% → exceeds sales_manager limit (2%)
            override_reason="Discount request",
            requested_by="bob",
            role="sales_manager",
        )
        with pytest.raises(HTTPException) as exc_info:
            svc.apply_pricing_override(pricing.id, req)
        assert exc_info.value.status_code == 422
        assert "Development Director" in exc_info.value.detail

    def test_development_director_within_threshold_succeeds(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV3")
        pricing = self._make_pricing(db_session, unit_id, 500_000.0)
        svc = UnitPricingService(db_session)

        req = PricingOverrideRequest(
            override_amount=20_000.0,  # 4% → within director limit
            override_reason="Bulk deal discount",
            requested_by="director1",
            role="development_director",
        )
        result = svc.apply_pricing_override(pricing.id, req)
        assert result.manual_adjustment == pytest.approx(20_000.0)
        assert result.final_price == pytest.approx(520_000.0)

    def test_development_director_above_threshold_raises(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV4")
        pricing = self._make_pricing(db_session, unit_id, 500_000.0)
        svc = UnitPricingService(db_session)

        req = PricingOverrideRequest(
            override_amount=30_000.0,  # 6% → exceeds director limit (5%)
            override_reason="Special client",
            requested_by="director2",
            role="development_director",
        )
        with pytest.raises(HTTPException) as exc_info:
            svc.apply_pricing_override(pricing.id, req)
        assert exc_info.value.status_code == 422
        assert "CEO" in exc_info.value.detail

    def test_ceo_unlimited_authority(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV5")
        pricing = self._make_pricing(db_session, unit_id, 500_000.0)
        svc = UnitPricingService(db_session)

        req = PricingOverrideRequest(
            override_amount=100_000.0,  # 20% → only CEO can approve
            override_reason="VIP client discount",
            requested_by="ceo_user",
            role="ceo",
        )
        result = svc.apply_pricing_override(pricing.id, req)
        assert result.manual_adjustment == pytest.approx(100_000.0)
        assert result.final_price == pytest.approx(600_000.0)

    def test_approved_pricing_cannot_be_overridden(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV6")
        pricing = self._make_pricing(db_session, unit_id)
        svc = UnitPricingService(db_session)

        # Approve the pricing record first.
        svc.approve_pricing(pricing.id, "approver1")

        req = PricingOverrideRequest(
            override_amount=5_000.0,
            override_reason="Post-approval override attempt",
            requested_by="alice",
            role="sales_manager",
        )
        with pytest.raises(HTTPException) as exc_info:
            svc.apply_pricing_override(pricing.id, req)
        assert exc_info.value.status_code == 422
        assert "approved" in exc_info.value.detail.lower()

    def test_archived_pricing_cannot_be_overridden(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV7")
        pricing = self._make_pricing(db_session, unit_id)
        svc = UnitPricingService(db_session)

        # Supersede to archive the record.
        from app.modules.pricing.schemas import UnitPricingCreate

        svc.create_pricing(unit_id, UnitPricingCreate(base_price=600_000.0))

        req = PricingOverrideRequest(
            override_amount=5_000.0,
            override_reason="Override on archived",
            requested_by="alice",
            role="sales_manager",
        )
        with pytest.raises(HTTPException) as exc_info:
            svc.apply_pricing_override(pricing.id, req)
        assert exc_info.value.status_code == 422

    def test_raises_404_for_unknown_pricing_id(self, db_session: Session):
        svc = UnitPricingService(db_session)
        req = PricingOverrideRequest(
            override_amount=1_000.0,
            override_reason="Test",
            requested_by="alice",
            role="ceo",
        )
        with pytest.raises(HTTPException) as exc_info:
            svc.apply_pricing_override("no-such-id", req)
        assert exc_info.value.status_code == 404

    def test_negative_final_price_raises(self, db_session: Session):
        unit_id = _make_unit(db_session, "PRJ-OV8")
        pricing = self._make_pricing(db_session, unit_id, 500_000.0)
        svc = UnitPricingService(db_session)

        req = PricingOverrideRequest(
            override_amount=-600_000.0,  # would make final_price negative
            override_reason="Extreme discount",
            requested_by="ceo_user",
            role="ceo",
        )
        with pytest.raises(HTTPException) as exc_info:
            svc.apply_pricing_override(pricing.id, req)
        assert exc_info.value.status_code == 422
        assert "negative" in exc_info.value.detail.lower()

    def test_unknown_role_rejected_by_schema(self, db_session: Session):
        """Invalid role values are now rejected at schema construction by Pydantic Literal validation."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError) as exc_info:
            PricingOverrideRequest(
                override_amount=1_000.0,
                override_reason="Test",
                requested_by="alice",
                role="wizard",  # not a valid Literal value
            )
        assert "role" in str(exc_info.value)


# ===========================================================================
# API integration tests — POST /pricing/{id}/override
# ===========================================================================


class TestOverrideEndpoint:
    def _setup(self, client: TestClient, proj_code: str) -> str:
        """Create hierarchy + pricing record. Returns pricing_id."""
        _, unit_id = _create_hierarchy(client, proj_code)
        client.post(
            f"/api/v1/pricing/unit/{unit_id}/attributes",
            json=_VALID_ATTRS_PAYLOAD,
        )
        pricing_id = client.post(
            f"/api/v1/units/{unit_id}/pricing",
            json={"base_price": 500_000.0},
        ).json()["id"]
        return pricing_id

    def test_override_within_threshold_returns_200(self, client: TestClient):
        pricing_id = self._setup(client, "PRJ-OVAPI1")
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 5_000.0,
                "override_reason": "Client negotiation",
                "requested_by": "alice",
                "role": "sales_manager",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["manual_adjustment"] == pytest.approx(5_000.0)
        assert data["final_price"] == pytest.approx(505_000.0)
        assert data["override_reason"] == "Client negotiation"
        assert data["override_requested_by"] == "alice"

    def test_override_above_threshold_returns_422(self, client: TestClient):
        pricing_id = self._setup(client, "PRJ-OVAPI2")
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 15_000.0,  # 3% > sales_manager limit
                "override_reason": "Discount",
                "requested_by": "alice",
                "role": "sales_manager",
            },
        )
        assert resp.status_code == 422
        assert "Development Director" in resp.json()["detail"]

    def test_override_approved_record_returns_422(self, client: TestClient):
        pricing_id = self._setup(client, "PRJ-OVAPI3")
        client.post(
            f"/api/v1/pricing/{pricing_id}/approve",
            json={"approved_by": "approver1"},
        )
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 5_000.0,
                "override_reason": "Post-approval attempt",
                "requested_by": "alice",
                "role": "sales_manager",
            },
        )
        assert resp.status_code == 422

    def test_override_not_found_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/pricing/no-such-id/override",
            json={
                "override_amount": 1_000.0,
                "override_reason": "Test",
                "requested_by": "alice",
                "role": "ceo",
            },
        )
        assert resp.status_code == 404

    def test_override_missing_reason_returns_422(self, client: TestClient):
        pricing_id = self._setup(client, "PRJ-OVAPI4")
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 1_000.0,
                # override_reason missing
                "requested_by": "alice",
                "role": "sales_manager",
            },
        )
        assert resp.status_code == 422


# ===========================================================================
# API integration tests — GET /pricing/{id}/premium-breakdown
# ===========================================================================


class TestPremiumBreakdownEndpoint:
    def _setup_with_attrs(self, client: TestClient, proj_code: str) -> str:
        """Create hierarchy, set attributes, create pricing. Returns pricing_id."""
        _, unit_id = _create_hierarchy(client, proj_code)
        client.post(
            f"/api/v1/pricing/unit/{unit_id}/attributes",
            json=_VALID_ATTRS_PAYLOAD,
        )
        pricing_id = client.post(
            f"/api/v1/units/{unit_id}/pricing",
            json={"base_price": 500_000.0},
        ).json()["id"]
        return pricing_id

    def _setup_without_attrs(self, client: TestClient, proj_code: str) -> str:
        """Create hierarchy, create pricing (no attrs). Returns pricing_id."""
        _, unit_id = _create_hierarchy(client, proj_code)
        pricing_id = client.post(
            f"/api/v1/units/{unit_id}/pricing",
            json={"base_price": 500_000.0},
        ).json()["id"]
        return pricing_id

    def test_breakdown_with_engine_data_returns_200(self, client: TestClient):
        pricing_id = self._setup_with_attrs(client, "PRJ-PBK1")
        resp = client.get(f"/api/v1/pricing/{pricing_id}/premium-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pricing_id"] == pricing_id
        assert data["has_engine_breakdown"] is True
        assert data["floor_premium"] == pytest.approx(10_000.0)
        assert data["view_premium"] == pytest.approx(15_000.0)
        assert data["corner_premium"] == pytest.approx(5_000.0)
        assert data["premium_total"] == pytest.approx(31_000.0)
        # base = 5000 * 100 = 500_000; final = 531_000
        assert data["engine_final_unit_price"] == pytest.approx(531_000.0)

    def test_breakdown_without_engine_data_has_engine_breakdown_false(
        self, client: TestClient
    ):
        pricing_id = self._setup_without_attrs(client, "PRJ-PBK2")
        resp = client.get(f"/api/v1/pricing/{pricing_id}/premium-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_engine_breakdown"] is False
        assert data["floor_premium"] is None
        assert data["premium_total"] is None
        assert data["engine_final_unit_price"] is None
        assert data["base_price"] == pytest.approx(500_000.0)

    def test_breakdown_not_found_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/pricing/no-such-id/premium-breakdown")
        assert resp.status_code == 404

    def test_breakdown_accuracy_matches_engine(self, client: TestClient):
        """Premium breakdown values must exactly match the pricing engine output."""
        pricing_id = self._setup_with_attrs(client, "PRJ-PBK3")
        breakdown = client.get(
            f"/api/v1/pricing/{pricing_id}/premium-breakdown"
        ).json()

        engine_price = client.get(
            f"/api/v1/pricing/unit/{breakdown['unit_id']}"
        ).json()

        assert breakdown["premium_total"] == pytest.approx(engine_price["premium_total"])
        assert breakdown["engine_final_unit_price"] == pytest.approx(
            engine_price["final_unit_price"]
        )


# ===========================================================================
# PR-14A: Override governance — PUT /pricing/{id} cannot bypass override rules
# ===========================================================================


class TestOverrideGovernancePutEndpoint:
    """Verify that PUT /pricing/{id} cannot be used to change manual_adjustment.

    All adjustment changes must flow through POST /pricing/{id}/override,
    which enforces role authority thresholds and records audit metadata.
    """

    def _setup(self, client: TestClient, proj_code: str) -> tuple[str, str]:
        """Create hierarchy + pricing record. Returns (unit_id, pricing_id)."""
        _, unit_id = _create_hierarchy(client, proj_code)
        pricing_id = client.post(
            f"/api/v1/units/{unit_id}/pricing",
            json={"base_price": 500_000.0},
        ).json()["id"]
        return unit_id, pricing_id

    def test_put_cannot_change_manual_adjustment(self, client: TestClient):
        """PUT /pricing/{id} with manual_adjustment must be rejected (422 — unknown field)."""
        _, pricing_id = self._setup(client, "PRJ-GOVPUT1")
        resp = client.put(
            f"/api/v1/pricing/{pricing_id}",
            json={"manual_adjustment": 10_000.0},
        )
        # Pydantic rejects unknown fields (or ignores them — either way
        # the adjustment must NOT be applied to the record).
        data = client.get(f"/api/v1/pricing/{pricing_id}/premium-breakdown").json()
        # manual_adjustment must remain 0.0 (default from creation)
        assert data["manual_adjustment"] == pytest.approx(0.0)

    def test_put_base_price_update_preserves_existing_adjustment(self, client: TestClient):
        """PUT /pricing/{id} updating base_price must keep existing manual_adjustment intact."""
        _, pricing_id = self._setup(client, "PRJ-GOVPUT2")

        # First apply an override via the correct endpoint.
        client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 5_000.0,
                "override_reason": "Client negotiation",
                "requested_by": "alice",
                "role": "sales_manager",
            },
        )

        # Now update base_price via PUT — manual_adjustment must be preserved.
        resp = client.put(
            f"/api/v1/pricing/{pricing_id}",
            json={"base_price": 550_000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["base_price"] == pytest.approx(550_000.0)
        # manual_adjustment from the override is preserved.
        assert data["manual_adjustment"] == pytest.approx(5_000.0)
        assert data["final_price"] == pytest.approx(555_000.0)

    def test_override_endpoint_remains_functional(self, client: TestClient):
        """POST /pricing/{id}/override must still work correctly after governance hardening."""
        _, pricing_id = self._setup(client, "PRJ-GOVPUT3")
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 10_000.0,
                "override_reason": "Special client discount",
                "requested_by": "director1",
                "role": "development_director",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["manual_adjustment"] == pytest.approx(10_000.0)
        assert data["final_price"] == pytest.approx(510_000.0)
        assert data["override_reason"] == "Special client discount"
        assert data["override_requested_by"] == "director1"

    def test_invalid_role_rejected_by_schema(self, client: TestClient):
        """POST /pricing/{id}/override with an invalid role is rejected at schema level."""
        _, pricing_id = self._setup(client, "PRJ-GOVPUT4")
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 1_000.0,
                "override_reason": "Test",
                "requested_by": "alice",
                "role": "wizard",  # not a valid Literal value
            },
        )
        assert resp.status_code == 422

    def test_governance_rule_sales_manager_cannot_exceed_threshold(self, client: TestClient):
        """Governance rules still enforced after hardening."""
        _, pricing_id = self._setup(client, "PRJ-GOVPUT5")
        resp = client.post(
            f"/api/v1/pricing/{pricing_id}/override",
            json={
                "override_amount": 20_000.0,  # 4% > sales_manager limit (2%)
                "override_reason": "Test",
                "requested_by": "alice",
                "role": "sales_manager",
            },
        )
        assert resp.status_code == 422
        assert "Development Director" in resp.json()["detail"]
