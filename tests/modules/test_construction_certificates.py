"""Certification: the one act in this module that becomes cost.

Everything before a certificate is intent — an authorisation, a commitment, a
change order. Certification is the statement that work was done, and it is what
a contractor invoices against and, where a milestone depends on it, what makes a
buyer's instalment fall due. So it carries four proofs, and the worked example
is pinned to the cent.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    certify,
    construction_url,
    create_certificate,
    record_invoice,
    set_certificate_line,
)


class TestTheWorkedExample:
    def test_the_first_certificate_withholds_retention_and_releases_none(
        self, finance_client: TestClient, project_id: str, certified_certificate: str
    ) -> None:
        """Given / When / Then: 200,000 less 20,000 retention nets 180,000."""
        detail = finance_client.get(
            f"{construction_url(project_id)}/certificates/{certified_certificate}"
        ).json()
        assert detail["current_work_value_ex_tax"] == "200000.00"
        assert detail["retention_held_amount"] == "20000.00"
        assert detail["retention_release_amount"] == "0.00"
        assert detail["advance_recovery_amount"] == "0.00"
        assert detail["other_deductions_amount"] == "0.00"
        assert detail["net_due"] == "180000.00"
        assert detail["status"] == "certified"

    def test_a_later_certificate_releasing_retention_reaches_the_pinned_figure(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """The calculator's worked example, end to end: 185,000 net due.

        200,000 of new work, less 10% retention on it (20,000), plus 5,000
        released out of the 20,000 the first certificate withheld.
        """
        created = create_certificate(
            finance_client,
            project_id,
            active_contract,
            certificate_number="IPC-REL-OK",
            period_start="2026-02-01",
            period_end="2026-02-28",
            certificate_date="2026-03-05",
            retention_release_amount="5000.00",
        )
        assert created.status_code == 201, created.text
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="200000.00",
            ).status_code
            == 200
        )
        certified = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert certified.status_code == 200, certified.text

        detail = certified.json()
        assert detail["current_work_value_ex_tax"] == "200000.00"
        assert detail["retention_held_amount"] == "20000.00"
        assert detail["retention_release_amount"] == "5000.00"
        assert detail["net_due"] == "185000.00"

    def test_certification_becomes_cost_and_nothing_else_does(
        self, finance_client: TestClient, project_id: str, certified_certificate: str
    ) -> None:
        """Certified-to-date moves. Nothing on the cash side does."""
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["cost_control"]["certified_to_date"] == "200000.00"
        assert summary["payable"]["confirmed_paid"] == "0.00"
        assert summary["payable"]["approved_invoice_payable"] == "0.00"

    def test_retention_is_held_not_deducted_from_cost(
        self, finance_client: TestClient, project_id: str, certified_certificate: str
    ) -> None:
        """Retention is cash timing. The cost is the work, at its full value."""
        contract = finance_client.get(
            f"{construction_url(project_id)}/contracts/"
            f"{finance_client.get(f'{construction_url(project_id)}/certificates/{certified_certificate}').json()['contract_id']}"
        ).json()
        assert contract["certified_to_date"] == "200000.00"
        assert contract["retention_held"] == "20000.00"
        assert contract["retention_released"] == "0.00"
        assert contract["retention_outstanding"] == "20000.00"


class TestTheFourProofs:
    def test_certifying_beyond_the_commitment_is_refused(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """Per cost code, not merely in total: a fitting total can hide an overrun."""
        created = create_certificate(
            finance_client, project_id, active_contract, certificate_number="IPC-OVER"
        )
        assert created.status_code == 201, created.text
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="1500000.00",
            ).status_code
            == 200
        )
        refused = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert refused.status_code == 409, refused.text
        assert "HRD-01" in refused.json()["detail"]

    def test_releasing_more_retention_than_is_held_is_refused(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """Money that was never withheld cannot be given back."""
        created = create_certificate(
            finance_client,
            project_id,
            active_contract,
            certificate_number="IPC-REL",
            retention_release_amount="50000.00",
        )
        assert created.status_code == 201, created.text
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="100000.00",
            ).status_code
            == 200
        )
        refused = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert refused.status_code == 409, refused.text

    def test_recovering_an_advance_that_was_never_paid_is_refused(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """An entitlement is not cash. Recovery measures against cash paid."""
        created = create_certificate(
            finance_client,
            project_id,
            active_contract,
            certificate_number="IPC-ADV",
            advance_recovery_amount="50000.00",
        )
        assert created.status_code == 201, created.text
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="100000.00",
            ).status_code
            == 200
        )
        refused = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert refused.status_code == 409, refused.text

    def test_a_certificate_whose_deductions_exceed_its_work_is_refused(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        """A negative valuation is a credit note, and this module is not one."""
        created = create_certificate(
            finance_client,
            project_id,
            active_contract,
            certificate_number="IPC-NEG",
            other_deductions_amount="90000.00",
        )
        assert created.status_code == 201, created.text
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="50000.00",
            ).status_code
            == 200
        )
        refused = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert refused.status_code == 422, refused.text
        assert "-45000.00" in refused.json()["detail"]


class TestCertifierIsNotThePreparer:
    """PR-MVP-09: the person who valued the work does not certify it."""

    def test_the_submitter_may_not_certify(
        self,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
    ) -> None:
        created = create_certificate(
            finance_client, project_id, active_contract, certificate_number="IPC-SELF"
        )
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="100000.00",
            ).status_code
            == 200
        )
        base = f"{construction_url(project_id)}/certificates/{certificate_id}"
        assert finance_client.post(f"{base}/submit", json={}).status_code == 200
        refused = finance_client.post(f"{base}/certify", json={})
        assert refused.status_code == 403, refused.text


class TestReversal:
    def test_a_certificate_an_approved_invoice_claims_against_cannot_be_reversed(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """A liability standing against a certificate that no longer exists."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        assert invoice.status_code == 201, invoice.text
        approved = second_finance_client.post(
            f"{construction_url(project_id)}/invoices/{invoice.json()['id']}/approve", json={}
        )
        assert approved.status_code == 200, approved.text

        refused = finance_client.post(
            f"{construction_url(project_id)}/certificates/{certified_certificate}/reverse",
            json={"reason": "Valuation disputed after issue"},
        )
        assert refused.status_code == 409, refused.text

    def test_an_invoice_against_a_reversed_certificate_cannot_be_approved(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """The ceiling is re-read at approval, not trusted from when it was recorded.

        A recorded invoice is only a document, so it does not block a reversal.
        That leaves the window this closes: reverse the certificate, then
        approve the invoice it named, and the liability would rest on an
        authorisation that has been withdrawn.
        """
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        assert invoice.status_code == 201, invoice.text
        reversed_response = finance_client.post(
            f"{construction_url(project_id)}/certificates/{certified_certificate}/reverse",
            json={"reason": "Measured quantities were wrong"},
        )
        assert reversed_response.status_code == 200, reversed_response.text

        refused = second_finance_client.post(
            f"{construction_url(project_id)}/invoices/{invoice.json()['id']}/approve", json={}
        )
        assert refused.status_code == 409, refused.text

    def test_reversing_a_certificate_removes_its_cost(
        self,
        finance_client: TestClient,
        project_id: str,
        certified_certificate: str,
    ) -> None:
        before = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert before["cost_control"]["certified_to_date"] == "200000.00"

        reversed_response = finance_client.post(
            f"{construction_url(project_id)}/certificates/{certified_certificate}/reverse",
            json={"reason": "Measured quantities were wrong"},
        )
        assert reversed_response.status_code == 200, reversed_response.text

        after = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert after["cost_control"]["certified_to_date"] == "0.00"


class TestCumulativeCertification:
    def test_a_second_certificate_shows_what_came_before(
        self,
        finance_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """Previously certified, this period, cumulative — three separate columns."""
        created = create_certificate(
            finance_client,
            project_id,
            active_contract,
            certificate_number="IPC-02",
            period_start="2026-02-01",
            period_end="2026-02-28",
            certificate_date="2026-03-05",
        )
        assert created.status_code == 201, created.text
        certificate_id = created.json()["id"]
        assert (
            set_certificate_line(
                finance_client,
                project_id,
                certificate_id,
                cost_code_id=cost_codes["hard"],
                current_work_value_ex_tax="300000.00",
            ).status_code
            == 200
        )
        certified = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert certified.status_code == 200, certified.text

        detail = certified.json()
        line = next(item for item in detail["lines"] if item["cost_code"] == "HRD-01")
        assert line["previously_certified"] == "200000.00"
        assert line["current_work_value_ex_tax"] == "300000.00"
        assert line["cumulative_certified"] == "500000.00"
