"""One denomination, proved rather than assumed.

There is no exchange rate anywhere in this platform, so every figure a
construction surface adds together has to be in the same currency or the sum is
meaningless. The discipline is the project's base currency, everywhere, refused
at the point of entry rather than filtered out at the point of reading.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.models import Currency
from tests.modules.conftest import (
    SETTINGS,
    construction_url,
    create_contract,
    record_payment,
)


def second_currency(admin_client: TestClient) -> str:
    response = admin_client.post(f"{SETTINGS}/currencies", json={"code": "EUR", "name": "Euro"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestContractsAreInTheProjectsCurrency:
    def test_a_contract_in_another_currency_is_refused_at_entry(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """Given / When / Then: refused when written, not hidden when read."""
        other = second_currency(admin_client)
        refused = create_contract(finance_client, project_id, other, contract_number="CT-EUR")
        assert refused.status_code == 422, refused.text

    def test_a_payment_in_another_currency_is_refused(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        active_contract: str,
    ) -> None:
        other = second_currency(admin_client)
        refused = record_payment(
            finance_client, project_id, active_contract, other, amount="1000.00"
        )
        assert refused.status_code == 422, refused.text


class TestEveryFigureStatesItsDenomination:
    def test_the_summary_names_the_currency_it_is_in(
        self, finance_client: TestClient, db: Session, project_id: str, active_budget: str
    ) -> None:
        """A money figure with no denomination is a number, not an amount."""
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        code = db.scalars(select(Currency.code).where(Currency.code == "JOD")).one()
        assert summary["currency_code"] == code

    def test_the_contract_file_names_the_currency_it_is_in(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        detail = finance_client.get(
            f"{construction_url(project_id)}/contracts/{active_contract}"
        ).json()
        assert detail["currency_code"] == "JOD"

    def test_the_budget_names_the_currency_it_is_in(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        detail = finance_client.get(
            f"{construction_url(project_id)}/budgets/{active_budget}"
        ).json()
        assert detail["currency_code"] == "JOD"


class TestReconciliationChecksTheDenomination:
    def test_the_reconciliation_proves_every_contract_is_in_base_currency(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        """A structural check, not a screen-level filter.

        The service refuses a foreign contract at entry, so this can only fail
        after somebody has reached the database directly — which is exactly the
        case a reconciliation exists to surface.
        """
        report = finance_client.get(f"{construction_url(project_id)}/reconciliation").json()
        currency_check = next(
            check for check in report["checks"] if "base currency" in check["label"]
        )
        assert currency_check["ok"] is True
        assert report["ok"] is True
