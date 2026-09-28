"""Marketing projections, project isolation and retained editing/deletion."""

import uuid
from decimal import Decimal as D
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.marketing.calculations import calculate
from app.modules.marketing.schemas import ScenarioWrite
from app.modules.projects.models import UserProjectAccess
from tests.factories import client_for, make_user
from tests.modules.conftest import PROJECTS, grant_access, inventory_url, project_payload


def root(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/marketing"


def scenario(currency_id: str, **changes: object) -> dict:
    return {
        "mode": "long_term",
        "currency_id": currency_id,
        "annual_rent_per_sqm": "120",
        "annual_expense_per_sqm": "30",
        "vacancy_percent": "0",
        "income_growth_percent": "0",
        "expense_growth_percent": "0",
        "appreciation_percent": "0",
        "exit_cap_percent": "5",
        "discount_percent": "0",
        "acquisition_cost_percent": "0",
        "selling_cost_percent": "0",
        "setup_cost": "0",
        "source": "Synthetic test assumptions",
        "as_of": "2026-09-27",
        **changes,
    }


def test_calculation_reconciles_cashflows_and_single_exit() -> None:
    s = ScenarioWrite(**scenario(str(uuid.uuid4())))
    p = calculate(s, D("100"), D("100000"))
    assert p.years[0].gross_revenue == D("12000")
    assert p.years[0].noi == D("9000")
    assert p.net_yield_percent == D("9")
    assert p.roi_percent == D("45")
    assert p.irr_percent == D("9")
    assert p.npv == D("45000")
    assert p.cap_value == D("180000")
    assert p.sale_proceeds == D("100000")
    assert p.years[-1].cashflow == D("109000")
    assert p.rental_payback_years is None
    assert p.total_payback_year == 5
    cap = calculate(s.model_copy(update={"exit_method": "cap_rate"}), D("100"), D("100000"))
    assert cap.sale_proceeds == D("180000")
    assert cap.roi_percent == D("125")
    loss = calculate(s.model_copy(update={"vacancy_percent": D("100")}), D("100"), D("100000"))
    assert loss.net_yield_percent == D("-3")
    assert loss.irr_percent is None
    assert loss.total_payback_year is None


def test_growth_fees_vacancy_and_discount() -> None:
    s = ScenarioWrite(
        **scenario(
            str(uuid.uuid4()),
            vacancy_percent="10",
            income_growth_percent="10",
            expense_growth_percent="5",
            appreciation_percent="10",
            acquisition_cost_percent="10",
            selling_cost_percent="5",
            setup_cost="10000",
            discount_percent="5",
        )
    )
    p = calculate(s, D("100"), D("100000"))
    assert p.initial_investment == D("120000")
    assert p.years[0].noi == D("7800")
    assert p.years[1].noi == D("8730")
    assert p.appreciation_value == D("161051")
    assert p.sale_proceeds == D("152998.45")
    assert p.net_yield_percent == D("6.50")
    assert p.npv < sum(row.cashflow for row in p.years) - p.initial_investment
    assert all(row.noi == row.effective_revenue - row.expenses for row in p.years)


def test_content_lifecycle(admin_client: TestClient, project_id: str, db: Session) -> None:
    base = root(project_id)
    assert admin_client.get(f"{base}/content/bio").json()["version"] == 0
    data = {
        "country": {"paragraph": "Country", "bullets": ["Point"]},
        "nearby": [{"name": "Airport", "duration_minutes": 20}],
        "amenities": ["Pool"],
    }
    saved = admin_client.put(f"{base}/content/bio", json={"expected_version": 0, "data": data})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["nearby"][0]["duration_minutes"] == 20
    assert (
        admin_client.put(
            f"{base}/content/bio", json={"expected_version": 0, "data": {}}
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            f"{base}/content/bio/delete", json={"expected_version": 1, "reason": "Test cleanup"}
        ).status_code
        == 204
    )
    assert (
        admin_client.post(
            f"{base}/content/bio/delete", json={"expected_version": 1, "reason": "Again"}
        ).status_code
        == 404
    )
    assert admin_client.get(f"{base}/content/bio").json()["version"] == 0
    assert db.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "marketing_content", AuditEvent.action == "delete"
        )
    ).before_data["data"]["amenities"] == ["Pool"]
    brand = {
        "project_name": "Example",
        "colors": [{"name": "Primary", "hex": "#123456"}],
        "fonts": [{"family": "Arial"}],
    }
    assert (
        admin_client.put(
            f"{base}/content/branding", json={"expected_version": 0, "data": brand}
        ).status_code
        == 200
    )
    bad = admin_client.put(
        f"{base}/content/branding",
        json={"expected_version": 1, "data": {"colors": [{"name": "Bad", "hex": "javascript:x"}]}},
    )
    assert bad.status_code == 422
    assert (
        admin_client.put(
            f"{base}/content/bio",
            json={"expected_version": 0, "data": {"roi_min_percent": "5", "roi_max_percent": "7"}},
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "role,write",
    [("sales_advisor", 403), ("sales_operations", 200), ("finance", 200), ("auditor", 403)],
)
def test_access(
    admin_client: TestClient, project_id: str, db: Session, role: str, write: int
) -> None:
    user = make_user(db, email=f"{role}@marketing.test", roles=(role,))
    client = client_for(user.email)
    base = root(project_id)
    assert client.get(f"{base}/content/bio").status_code == 404
    grant_access(admin_client, project_id, user)
    assert client.get(f"{base}/content/bio").status_code == 200
    assert (
        client.put(f"{base}/content/bio", json={"expected_version": 0, "data": {}}).status_code
        == write
    )
    if write == 403:
        assert (
            client.post(
                f"{base}/content/bio/delete", json={"expected_version": 1, "reason": "Denied"}
            ).status_code
            == 403
        )
    access = db.scalar(select(UserProjectAccess).where(UserProjectAccess.user_id == user.id))
    access.phase_scope = "selected"
    db.commit()
    assert client.get(f"{base}/scenarios").status_code == 404
    assert client.get(f"{base}/units").status_code == 404


def test_projections_and_override(
    admin_client: TestClient,
    project_id: str,
    currency_id: str,
    unit_id: str,
    area_types: dict[str, str],
) -> None:
    base = root(project_id)
    default = admin_client.post(f"{base}/scenarios", json=scenario(currency_id))
    assert default.status_code == 201, default.text
    assert admin_client.post(f"{base}/scenarios", json=scenario(currency_id)).status_code == 409
    result = admin_client.get(f"{base}/units").json()["units"][0]
    assert result["scenarios"][0]["projection"] is None
    url = f"{inventory_url(project_id)}/units/{unit_id}"
    area = admin_client.post(
        f"{url}/area-schedules",
        json={
            "revision_code": "M1",
            "reconciled": True,
            "values": [{"area_type_id": area_types["INTERNAL"], "raw_area": "100"}],
        },
    )
    assert area.status_code == 201, area.text
    assert admin_client.post(f"{url}/area-schedules/{area.json()['id']}/approve").status_code == 200
    body = scenario(currency_id, unit_id=unit_id, price_override="100000")
    unit = admin_client.post(f"{base}/scenarios", json=body)
    assert unit.status_code == 201, unit.text
    results = admin_client.get(f"{base}/units").json()
    assert results["total"] == 1
    result = results["units"][0]["scenarios"][0]
    assert result["source_scope"] == "Unit override"
    assert result["projection"]["net_yield_percent"] == "9.00"
    assert result["projection"]["sale_proceeds"] == "100000.00"
    assert admin_client.get(f"{base}/units?search=not-found").json()["total"] == 0
    record = unit.json()
    assert admin_client.put(f"{base}/scenarios/{record['id']}", json=body).status_code == 409
    assert (
        admin_client.post(
            f"{base}/scenarios/{record['id']}/delete",
            json={"expected_version": 1, "reason": "Remove override"},
        ).status_code
        == 204
    )
    assert (
        admin_client.get(f"{base}/units").json()["units"][0]["scenarios"][0]["source_scope"]
        == "Project default"
    )
    assert (
        admin_client.post(
            f"{base}/scenarios/{record['id']}/delete",
            json={"expected_version": 1, "reason": "Again"},
        ).status_code
        == 404
    )


def test_indicator_edit_delete_scope(
    admin_client: TestClient, project_id: str, country_pack_id: str, currency_id: str
) -> None:
    base = root(project_id)
    body = {
        "name": "Inflation",
        "geography": "Test country",
        "value": "-0.5",
        "unit": "%",
        "period": "2026 Q2",
        "as_of": "2026-09-01",
        "source": "Synthetic test source",
    }
    result = admin_client.post(f"{base}/indicators", json=body)
    assert result.status_code == 201, result.text
    row = result.json()
    second = admin_client.post(
        PROJECTS, json=project_payload(country_pack_id, currency_id, code="OTHER")
    ).json()["id"]
    assert (
        admin_client.put(
            f"{root(second)}/indicators/{row['id']}", json={**body, "expected_version": 1}
        ).status_code
        == 404
    )
    assert (
        admin_client.put(
            f"{base}/indicators/{row['id']}", json={**body, "expected_version": 1, "value": "1.2"}
        ).status_code
        == 200
    )
    assert (
        admin_client.post(
            f"{base}/indicators/{row['id']}/delete",
            json={"expected_version": 1, "reason": "Old revision"},
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            f"{base}/indicators/{row['id']}/delete",
            json={"expected_version": 2, "reason": "Corrected"},
        ).status_code
        == 204
    )
    assert admin_client.get(f"{base}/indicators").json() == []
    assert (
        admin_client.post(
            f"{base}/scenarios", json=scenario(currency_id, unit_id=str(uuid.uuid4()))
        ).status_code
        == 404
    )
    assert (
        admin_client.post(
            f"{base}/scenarios", json=scenario(currency_id, vacancy_percent="101")
        ).status_code
        == 422
    )


def test_migration_roundtrip_and_retention(
    admin_client: TestClient, project_id: str, db: Session
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    db.rollback()
    command.downgrade(config, "0038_commission_beneficiaries")
    command.upgrade(config, "head")
    command.check(config)
    assert (
        admin_client.put(
            f"{root(project_id)}/content/bio", json={"expected_version": 0, "data": {}}
        ).status_code
        == 200
    )
    assert (
        admin_client.post(
            f"{root(project_id)}/content/bio/delete",
            json={"expected_version": 1, "reason": "Retain"},
        ).status_code
        == 204
    )
    db.rollback()
    with pytest.raises(RuntimeError, match="Marketing history"):
        command.downgrade(config, "0038_commission_beneficiaries")
    assert db.scalar(text("SELECT count(*) FROM marketing_content")) == 1
