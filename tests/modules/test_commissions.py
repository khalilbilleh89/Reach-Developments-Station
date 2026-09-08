"""Focused commission calculation, reconciliation and maker/checker tests."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.commissions.service import _terms


@pytest.fixture(autouse=True)
def clean_commission_rows(db: Session) -> Iterator[None]:
    yield
    db.execute(text("TRUNCATE commission_allocations, commission_grants CASCADE"))
    db.commit()


def root(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/commissions"


def test_150k_golden_decimal_calculation() -> None:
    base, total = _terms(Decimal("150000"), Decimal("0.10"), Decimal("150000"))
    assert base == Decimal("150000.00")
    assert total == Decimal("15000.00")


def test_reconciliation_and_maker_checker(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    active_sale: str,
) -> None:
    eligible = finance_client.get(f"{root(project_id)}/eligible-sales").json()
    sold_price = eligible[0]["sold_price"]
    created = finance_client.post(
        root(project_id),
        json={
            "sale_contract_id": active_sale,
            "commissionable_base_amount": sold_price,
            "granted_rate_fraction": "0.100000",
        },
    )
    assert created.status_code == 201, created.text
    grant = created.json()
    assert grant["sold_price_snapshot"] == sold_price
    expected_total = str((Decimal(sold_price) * Decimal("0.1")).quantize(Decimal("0.01")))
    assert grant["commission_total"] == expected_total
    for beneficiary, rate in (
        ("Branch", "0.050000"),
        ("Sales Person", "0.030000"),
        ("Cyprus Branch", "0.010000"),
        ("Support Team", "0.010000"),
    ):
        added = finance_client.post(
            f"{root(project_id)}/{grant['id']}/allocations",
            json={"beneficiary_name": beneficiary, "rate_fraction": rate},
        )
        assert added.status_code == 200, added.text
        grant = added.json()
    assert grant["allocation_rate_total"] == "0.100000"
    assert grant["allocation_amount_total"] == expected_total
    assert grant["is_reconciled"] is True
    assert finance_client.post(f"{root(project_id)}/{grant['id']}/release").status_code == 403
    released = cfo_client.post(f"{root(project_id)}/{grant['id']}/release")
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "released"
    assert (
        finance_client.post(
            f"{root(project_id)}/{grant['id']}/allocations",
            json={"beneficiary_name": "Late", "rate_fraction": "0.010000"},
        ).status_code
        == 409
    )


def test_partial_base_and_invalid_terms(
    finance_client: TestClient, project_id: str, active_sale: str
) -> None:
    sold = Decimal(finance_client.get(f"{root(project_id)}/eligible-sales").json()[0]["sold_price"])
    base = (sold / 2).quantize(Decimal("0.01"))
    partial = finance_client.post(
        root(project_id),
        json={
            "sale_contract_id": active_sale,
            "commissionable_base_amount": str(base),
            "granted_rate_fraction": "0.1",
        },
    )
    assert partial.status_code == 201, partial.text
    assert partial.json()["commission_total"] == str(
        (base * Decimal("0.1")).quantize(Decimal("0.01"))
    )
