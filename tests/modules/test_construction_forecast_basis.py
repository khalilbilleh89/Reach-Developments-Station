"""What a forecast was built on, and what today's figures may not rewrite.

Four separations, and each one was a way for a single number to mean two things.

**The cutoff is the formal certification.** A valuation dated inside a forecast's
period but signed off after its cutoff stays outside it. A certificate's document
date is a claim about when work was valued; ``certified_at`` is the fact of
somebody accepting it, and only the second one can put cost into a forecast that
was approved before it happened.

**Certified to date is today's figure; the estimate at completion is not.** The
estimate stays on the basis its own forecast was approved against, and that
frozen basis is reported beside it rather than left to be inferred by
subtraction.

**A forecast is measured against a budget somebody authorised.** Draft, submitted
and rejected budgets govern nothing.

**A contract's commitment is reported at the grain that owns it.** Two lines
naming one cost code are two lines, but one commitment.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    at,
    backdate,
    certify,
    construction_summary,
    construction_url,
    cover_budget,
    create_budget,
    create_certificate,
    create_contract,
    create_forecast,
    govern_budget,
    govern_contract,
    govern_forecast,
    set_certificate_line,
    set_contract_line,
    set_forecast_line,
)

#: The forecast used throughout: every cost code covered, hard forecast at
#: 10,300,000 against a 10,000,000 authorisation. Nothing else in the file
#: depends on the split, only on it being the same one every time.
FORECAST_COVER = {
    "hard": "10300000.00",
    "soft": "1000000.00",
    "contingency": "500000.00",
    "other": "250000.00",
}

#: What those four lines add up to, and therefore the estimate at completion of
#: a forecast whose certified basis is nothing.
FORECAST_REMAINING = "12050000.00"


def days_ago(count: int) -> date:
    """A business date ``count`` days back.

    Relative rather than fixed because a forecast may not be taken as at a
    future date, so a hard-coded cutoff would pass until the calendar reached it
    and fail every day afterwards.
    """
    return date.today() - timedelta(days=count)


def cover_forecast(
    client: TestClient,
    project_id: str,
    version_id: str,
    cost_codes: dict[str, str],
) -> None:
    """Forecast every active cost code, which is what submission insists on."""
    for category, amount in FORECAST_COVER.items():
        response = set_forecast_line(
            client,
            project_id,
            version_id,
            cost_code_id=cost_codes[category],
            forecast_remaining_amount_ex_tax=amount,
        )
        assert response.status_code == 200, response.text


def governed_forecast(
    preparer: TestClient,
    approver: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    *,
    as_of: date,
    change_reason: str = "Month-end forecast",
) -> str:
    """One forecast, covered and put in force as at a stated cutoff."""
    created = create_forecast(
        preparer, project_id, as_of_date=as_of.isoformat(), change_reason=change_reason
    )
    assert created.status_code == 201, created.text
    version_id: str = created.json()["id"]
    cover_forecast(preparer, project_id, version_id, cost_codes)
    activated = govern_forecast(preparer, approver, project_id, version_id)
    assert activated.status_code == 200, activated.text
    return version_id


def certified_work(
    preparer: TestClient,
    certifier: TestClient,
    project_id: str,
    contract_id: str,
    cost_code_id: str,
    *,
    number: str,
    amount: str,
    certificate_date: date,
) -> str:
    """One certificate, drafted and certified, returning its identifier.

    ``certified_at`` is stamped by the certification itself and is therefore
    always now. Where a test needs it earlier, it moves it with ``backdate``.
    """
    created = create_certificate(
        preparer,
        project_id,
        contract_id,
        certificate_number=number,
        period_start=(certificate_date - timedelta(days=30)).isoformat(),
        period_end=certificate_date.isoformat(),
        certificate_date=certificate_date.isoformat(),
    )
    assert created.status_code == 201, created.text
    certificate_id: str = created.json()["id"]
    line = set_certificate_line(
        preparer,
        project_id,
        certificate_id,
        cost_code_id=cost_code_id,
        current_work_value_ex_tax=amount,
    )
    assert line.status_code == 200, line.text
    certified = certify(preparer, certifier, project_id, certificate_id)
    assert certified.status_code == 200, certified.text
    return certificate_id


def forecast_detail(client: TestClient, project_id: str, version_id: str) -> dict[str, Any]:
    response = client.get(f"{construction_url(project_id)}/forecasts/{version_id}")
    assert response.status_code == 200, response.text
    detail: dict[str, Any] = response.json()
    return detail


@pytest.fixture
def valued_before_certified(
    finance_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_contract: str,
) -> str:
    """200,000 of work valued to three days ago and certified today.

    The ordinary shape of a valuation: a period closes, somebody reads it, and
    the signature lands days later. No arrangement is needed to produce it —
    certification stamps now, and the document date is stated on the form.
    """
    return certified_work(
        finance_client,
        manager_member_client,
        project_id,
        active_contract,
        cost_codes["hard"],
        number="IPC-01",
        amount="200000.00",
        certificate_date=days_ago(3),
    )


@pytest.fixture
def forecast_over_history(
    db: Session,
    finance_client: TestClient,
    cfo_client: TestClient,
    manager_member_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_contract: str,
) -> str:
    """200,000 certified five days ago, under a forecast taken as at two days ago.

    Here the certificate is genuinely inside the forecast's basis, which is what
    lets the tests below distinguish "the cutoff excluded it" from "there was
    never anything to exclude".
    """
    certificate_id = certified_work(
        finance_client,
        manager_member_client,
        project_id,
        active_contract,
        cost_codes["hard"],
        number="IPC-01",
        amount="200000.00",
        certificate_date=days_ago(6),
    )
    backdate(
        db,
        table="construction_certificates",
        row_id=certificate_id,
        certified_at=at(days_ago(5)),
    )
    return governed_forecast(finance_client, cfo_client, project_id, cost_codes, as_of=days_ago(2))


class TestTheCutoffIsFormalCertification:
    def test_a_valuation_signed_off_after_the_cutoff_stays_outside_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        valued_before_certified: str,
    ) -> None:
        """Given / When / Then: dated inside, certified outside, therefore outside.

        The certificate is dated three days ago and certified today. A forecast
        taken as at three days ago could not have contained it, because on that
        date nobody had certified the work. Cutting off on the document date
        would put 200,000 inside a forecast that was approved without it — a
        certified basis produced entirely by a backdated form.
        """
        version_id = governed_forecast(
            finance_client, cfo_client, project_id, cost_codes, as_of=days_ago(3)
        )

        detail = forecast_detail(finance_client, project_id, version_id)
        hard_line = next(line for line in detail["lines"] if line["cost_code"] == "HRD-01")
        assert hard_line["certified_to_date"] == "0.00"
        assert detail["total_certified"] == "0.00"
        assert detail["total_estimate_at_completion"] == FORECAST_REMAINING

        summary = construction_summary(finance_client, project_id)
        assert summary["cost_control"]["forecast_certified_as_of"] == "0.00"
        assert summary["cost_control"]["estimate_at_completion"] == FORECAST_REMAINING

    def test_a_later_cutoff_takes_the_same_work_in(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        valued_before_certified: str,
    ) -> None:
        """The rule is a cutoff, not an exclusion. Certified today is in today."""
        version_id = governed_forecast(
            finance_client, cfo_client, project_id, cost_codes, as_of=date.today()
        )

        detail = forecast_detail(finance_client, project_id, version_id)
        hard_line = next(line for line in detail["lines"] if line["cost_code"] == "HRD-01")
        assert hard_line["certified_to_date"] == "200000.00"
        assert detail["total_certified"] == "200000.00"
        assert detail["total_estimate_at_completion"] == "12250000.00"

    def test_certifying_more_does_not_rewrite_a_forecast_already_in_force(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        forecast_over_history: str,
    ) -> None:
        """Reproducibility: the forecast answers what it thought, not what is true now.

        200,000 was certified five days ago and is inside the forecast taken as
        at two days ago. Another 300,000 is certified today, after that cutoff.
        Re-opening the forecast must still show 200,000 — otherwise a governed
        estimate quietly grows every time somebody signs a valuation, and the
        figure Finance approved cannot be produced again.
        """
        before = forecast_detail(finance_client, project_id, forecast_over_history)
        assert before["total_certified"] == "200000.00"
        assert before["total_estimate_at_completion"] == "12250000.00"

        certified_work(
            finance_client,
            manager_member_client,
            project_id,
            active_contract,
            cost_codes["hard"],
            number="IPC-02",
            amount="300000.00",
            certificate_date=date.today(),
        )

        after = forecast_detail(finance_client, project_id, forecast_over_history)
        assert after["total_certified"] == "200000.00"
        assert after["total_estimate_at_completion"] == "12250000.00"
        assert after["total_variance_at_completion"] == before["total_variance_at_completion"]


class TestTheSummaryIsCurrentAndTheEstimateIsFrozen:
    def test_certifying_after_the_cutoff_moves_one_figure_and_not_the_other(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        forecast_over_history: str,
    ) -> None:
        """Two questions, two figures, and neither answers the other.

        "What has been certified?" is a question about now, and the command
        centre must answer it with 500,000 the moment the second certificate is
        signed. "What will this cost?" is the standing forecast's answer, and it
        is 200,000 certified plus the 12,050,000 that forecast said was left.
        Refreshing the first figure inside the second would count the new
        300,000 twice — once as certified, and again inside a remainder written
        before it existed.
        """
        opening = construction_summary(finance_client, project_id)["cost_control"]
        assert opening["certified_to_date"] == "200000.00"
        assert opening["forecast_certified_as_of"] == "200000.00"
        assert opening["estimate_at_completion"] == "12250000.00"

        certified_work(
            finance_client,
            manager_member_client,
            project_id,
            active_contract,
            cost_codes["hard"],
            number="IPC-02",
            amount="300000.00",
            certificate_date=date.today(),
        )

        cost = construction_summary(finance_client, project_id)["cost_control"]
        assert cost["certified_to_date"] == "500000.00"
        assert cost["forecast_certified_as_of"] == "200000.00"
        assert cost["forecast_remaining"] == FORECAST_REMAINING
        assert cost["estimate_at_completion"] == "12250000.00"
        assert cost["variance_at_completion"] == opening["variance_at_completion"]

    def test_with_no_forecast_in_force_there_is_no_frozen_basis_to_report(
        self,
        finance_client: TestClient,
        project_id: str,
        certified_certificate: str,
    ) -> None:
        """Absent, not zero. Nothing has fixed a basis, so there is none to state."""
        cost = construction_summary(finance_client, project_id)["cost_control"]
        assert cost["certified_to_date"] == "200000.00"
        assert cost["forecast_certified_as_of"] is None
        assert cost["estimate_at_completion"] is None


@pytest.fixture
def second_budget(
    finance_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> str:
    """A second budget version, in draft, with every cost code authorised."""
    created = create_budget(
        finance_client,
        project_id,
        effective_date=date.today().isoformat(),
        change_reason="Revision",
    )
    assert created.status_code == 201, created.text
    version_id: str = created.json()["id"]
    cover_budget(
        finance_client,
        project_id,
        version_id,
        cost_codes,
        hard="10000000.00",
        soft="1000000.00",
        contingency="500000.00",
        other="250000.00",
    )
    return version_id


class TestAForecastNeedsAnAuthorisedBudget:
    def test_a_draft_budget_may_not_govern_a_forecast(
        self, finance_client: TestClient, project_id: str, second_budget: str
    ) -> None:
        """A variance against a working paper is not a variance."""
        refused = create_forecast(finance_client, project_id, budget_version_id=second_budget)
        assert refused.status_code == 409, refused.text
        assert "draft" in refused.json()["detail"].lower()

    def test_a_submitted_budget_may_not_govern_a_forecast(
        self, finance_client: TestClient, project_id: str, second_budget: str
    ) -> None:
        """Waiting for a decision is not the same as having one."""
        base = f"{construction_url(project_id)}/budgets/{second_budget}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200

        refused = create_forecast(finance_client, project_id, budget_version_id=second_budget)
        assert refused.status_code == 409, refused.text
        assert "submitted" in refused.json()["detail"].lower()

    def test_a_rejected_budget_may_not_govern_a_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        second_budget: str,
    ) -> None:
        """The one status somebody explicitly declined to authorise."""
        base = f"{construction_url(project_id)}/budgets/{second_budget}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        rejected = cfo_client.post(f"{base}/reject", json={"reason": "Escalation not funded"})
        assert rejected.status_code == 200, rejected.text

        refused = create_forecast(finance_client, project_id, budget_version_id=second_budget)
        assert refused.status_code == 409, refused.text
        assert "rejected" in refused.json()["detail"].lower()

    def test_an_approved_budget_may_govern_a_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        second_budget: str,
    ) -> None:
        """Approved is an authorisation. Activation is a separate question."""
        base = f"{construction_url(project_id)}/budgets/{second_budget}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        approved = cfo_client.post(f"{base}/approve", json={"reason": "Authorised"})
        assert approved.status_code == 200, approved.text

        opened = create_forecast(finance_client, project_id, budget_version_id=second_budget)
        assert opened.status_code == 201, opened.text
        assert opened.json()["budget_version_number"] == 2

    def test_a_superseded_budget_may_still_govern_a_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        active_budget: str,
        second_budget: str,
    ) -> None:
        """A replaced authorisation was still an authorisation.

        Refusing it would make every forecast measured against last quarter's
        budget unreadable the moment this quarter's was activated, which is the
        opposite of what a named budget version is for.
        """
        assert (
            govern_budget(finance_client, cfo_client, project_id, second_budget).status_code == 200
        )

        opened = create_forecast(finance_client, project_id, budget_version_id=active_budget)
        assert opened.status_code == 201, opened.text
        assert opened.json()["budget_version_number"] == 1

    def test_the_budget_in_force_may_govern_a_forecast(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """The ordinary case, stated so the permitted set is complete here."""
        opened = create_forecast(finance_client, project_id, budget_version_id=active_budget)
        assert opened.status_code == 201, opened.text
        assert opened.json()["budget_version_number"] == 1

    def test_a_budget_superseded_under_an_open_forecast_still_carries_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
        second_budget: str,
    ) -> None:
        """The budget is re-read at submission and again at activation.

        This forecast is opened against version 1 while version 1 is in force,
        and version 2 is activated underneath it before it is submitted. Both
        later gates therefore ask the question again about a budget whose status
        has moved since the draft was opened, and both must accept it: version 1
        is superseded, not withdrawn, and the forecast stays measured against
        the authorisation it named rather than silently re-pointing at version 2.
        """
        opened = create_forecast(finance_client, project_id)
        assert opened.status_code == 201, opened.text
        version_id = opened.json()["id"]
        assert opened.json()["budget_version_number"] == 1
        cover_forecast(finance_client, project_id, version_id, cost_codes)

        assert (
            govern_budget(finance_client, cfo_client, project_id, second_budget).status_code == 200
        )
        superseded = finance_client.get(
            f"{construction_url(project_id)}/budgets/{active_budget}"
        ).json()
        assert superseded["status"] == "superseded"

        base = f"{construction_url(project_id)}/forecasts/{version_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        approved = cfo_client.post(f"{base}/approve", json={"reason": "Reviewed"})
        assert approved.status_code == 200, approved.text
        activated = finance_client.post(f"{base}/activate", json={})
        assert activated.status_code == 200, activated.text
        assert activated.json()["status"] == "active"
        assert activated.json()["budget_version_number"] == 1


@pytest.fixture
def split_contract(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    currency_id: str,
    cost_codes: dict[str, str],
    active_budget: str,
) -> str:
    """1,000,000 signed as two lines that name the same cost code.

    Entirely ordinary — preliminaries and superstructure booked to one code, or
    a schedule of rates split across pages — and the case where a per-line
    commitment figure stops being arithmetic and starts being double counting.
    """
    created = create_contract(
        finance_client,
        project_id,
        currency_id,
        contract_number="CT-SPLIT",
        retention_rate_fraction="0.1000",
    )
    assert created.status_code == 201, created.text
    contract_id: str = created.json()["id"]
    for sequence, amount, description in (
        (1, "600000.00", "Substructure"),
        (2, "400000.00", "Superstructure"),
    ):
        line = set_contract_line(
            finance_client,
            project_id,
            contract_id,
            sequence=sequence,
            cost_code_id=cost_codes["hard"],
            original_amount_ex_tax=amount,
            description=description,
        )
        assert line.status_code == 200, line.text
    activated = govern_contract(finance_client, cfo_client, project_id, contract_id)
    assert activated.status_code == 200, activated.text
    return contract_id


class TestOneCostCodeOnTwoContractLines:
    def test_a_line_carries_only_what_was_signed_on_it(
        self, finance_client: TestClient, project_id: str, split_contract: str
    ) -> None:
        """A line has an original value and nothing derived, because nothing is.

        The commitment a line would have to report is the cost code's, and both
        of these lines would report all of it. A field that is right on a
        one-line-per-code contract and doubles on this one is not a field worth
        keeping — a variation moves a cost code, not a line, so there is no
        honest way to give a line its own share of one.
        """
        detail = finance_client.get(
            f"{construction_url(project_id)}/contracts/{split_contract}"
        ).json()

        assert [line["original_amount_ex_tax"] for line in detail["lines"]] == [
            "600000.00",
            "400000.00",
        ]
        for line in detail["lines"]:
            assert line["cost_code"] == "HRD-01"
            assert "revised_commitment" not in line
            assert "certified_to_date" not in line

    def test_the_cost_code_position_is_stated_once(
        self, finance_client: TestClient, project_id: str, split_contract: str
    ) -> None:
        """Two lines, one code, one commitment — and it ties to the header."""
        detail = finance_client.get(
            f"{construction_url(project_id)}/contracts/{split_contract}"
        ).json()

        assert len(detail["cost_code_position"]) == 1
        position = detail["cost_code_position"][0]
        assert position["cost_code"] == "HRD-01"
        assert position["original_amount_ex_tax"] == "1000000.00"
        assert position["approved_variation_delta"] == "0.00"
        assert position["revised_commitment"] == "1000000.00"
        assert position["certified_to_date"] == "0.00"

        assert position["revised_commitment"] == detail["revised_commitment"]
        assert position["original_amount_ex_tax"] == detail["original_contract_value_ex_tax"]

    def test_certified_work_is_not_counted_once_per_line(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        split_contract: str,
    ) -> None:
        """200,000 certified against the code is 200,000, not 400,000."""
        certified_work(
            finance_client,
            manager_member_client,
            project_id,
            split_contract,
            cost_codes["hard"],
            number="IPC-01",
            amount="200000.00",
            certificate_date=days_ago(1),
        )

        detail = finance_client.get(
            f"{construction_url(project_id)}/contracts/{split_contract}"
        ).json()
        assert len(detail["cost_code_position"]) == 1
        assert detail["cost_code_position"][0]["certified_to_date"] == "200000.00"
        assert detail["certified_to_date"] == "200000.00"

        summary = construction_summary(finance_client, project_id)
        assert summary["cost_control"]["certified_to_date"] == "200000.00"
