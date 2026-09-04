"""Liability and cash: two more truths, kept apart from certification.

A certificate is what the work was worth. An invoice is what the vendor claims
and, once approved, what the company owes. A payment is cash actually leaving.
Nothing here collapses those into one number, and nothing here lets a claim
exist without a ceiling somebody authorised.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.modules.conftest import construction_url, record_invoice, record_payment


def approve_invoice(client: TestClient, project_id: str, invoice_id: str) -> None:
    response = client.post(f"{construction_url(project_id)}/invoices/{invoice_id}/approve", json={})
    assert response.status_code == 200, response.text


def allocate(
    client: TestClient,
    project_id: str,
    payment_id: str,
    *,
    invoice_id: str,
    amount: str,
) -> None:
    response = client.put(
        f"{construction_url(project_id)}/payments/{payment_id}/allocations",
        json={"invoice_id": invoice_id, "amount": amount},
    )
    assert response.status_code == 200, response.text


class TestEveryClaimHasACeiling:
    """PR-MVP-09 foundation fix: no invoice type escapes its authorisation."""

    def test_a_progress_invoice_must_name_a_certificate(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        refused = record_invoice(finance_client, project_id, active_contract)
        assert refused.status_code == 422, refused.text

    def test_an_other_invoice_must_name_a_certificate_too(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        """Given / When / Then: "other" was the escape hatch, and is not one."""
        refused = record_invoice(
            finance_client,
            project_id,
            active_contract,
            invoice_number="INV-OTHER",
            invoice_type="other",
            amount_ex_tax="500000.00",
        )
        assert refused.status_code == 422, refused.text

    def test_a_retention_release_invoice_must_name_a_certificate(
        self, finance_client: TestClient, project_id: str, active_contract: str
    ) -> None:
        refused = record_invoice(
            finance_client,
            project_id,
            active_contract,
            invoice_number="INV-RET",
            invoice_type="retention_release",
            amount_ex_tax="5000.00",
        )
        assert refused.status_code == 422, refused.text

    def test_an_advance_invoice_needs_no_certificate_but_has_an_entitlement(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        active_contract: str,
    ) -> None:
        """The advance's ceiling is the contract's entitlement, which is 100,000."""
        within = record_invoice(
            finance_client,
            project_id,
            active_contract,
            invoice_number="INV-ADV",
            invoice_type="advance",
            amount_ex_tax="100000.00",
        )
        assert within.status_code == 201, within.text
        approve_invoice(second_finance_client, project_id, within.json()["id"])

        beyond = record_invoice(
            finance_client,
            project_id,
            active_contract,
            invoice_number="INV-ADV-2",
            invoice_type="advance",
            amount_ex_tax="1.00",
        )
        assert beyond.status_code == 201, beyond.text
        refused = second_finance_client.post(
            f"{construction_url(project_id)}/invoices/{beyond.json()['id']}/approve", json={}
        )
        assert refused.status_code == 409, refused.text

    def test_a_progress_invoice_cannot_exceed_its_certificate(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """The certificate nets 180,000. A claim of 200,000 against it is refused."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="200000.00",
        )
        assert invoice.status_code == 201, invoice.text
        refused = second_finance_client.post(
            f"{construction_url(project_id)}/invoices/{invoice.json()['id']}/approve", json={}
        )
        assert refused.status_code == 409, refused.text


class TestRecordedIsNotOwed:
    def test_a_recorded_invoice_is_not_a_liability(
        self,
        finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """A document arriving in the post is not an obligation."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        assert invoice.status_code == 201, invoice.text
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["payable"]["approved_invoice_payable"] == "0.00"

    def test_an_approved_invoice_is_a_liability(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        approve_invoice(second_finance_client, project_id, invoice.json()["id"])
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["payable"]["approved_invoice_payable"] == "180000.00"
        assert summary["payable"]["invoice_outstanding"] == "180000.00"
        assert summary["payable"]["confirmed_paid"] == "0.00"

    def test_the_recorder_of_an_invoice_may_not_approve_it(
        self,
        finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """PR-MVP-09 foundation fix: approving creates a liability."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        refused = finance_client.post(
            f"{construction_url(project_id)}/invoices/{invoice.json()['id']}/approve", json={}
        )
        assert refused.status_code == 403, refused.text


class TestDisputeStandsTheLiability:
    def test_a_disputed_invoice_is_still_owed(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """An obligation that vanished on objection would make the ledger opinion."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        invoice_id = invoice.json()["id"]
        approve_invoice(second_finance_client, project_id, invoice_id)
        disputed = finance_client.post(
            f"{construction_url(project_id)}/invoices/{invoice_id}/dispute",
            json={"reason": "Quantities do not match the measure"},
        )
        assert disputed.status_code == 200, disputed.text

        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["payable"]["disputed_invoice_payable"] == "180000.00"
        assert summary["payable"]["invoice_outstanding"] == "180000.00"


class TestPaymentDiscipline:
    def test_the_recorder_of_a_payment_may_not_confirm_it(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """One person who can prepare and release cash is the classic failure."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        invoice_id = invoice.json()["id"]
        approve_invoice(second_finance_client, project_id, invoice_id)

        payment = record_payment(
            finance_client, project_id, active_contract, currency_id, amount="180000.00"
        )
        assert payment.status_code == 201, payment.text
        payment_id = payment.json()["id"]
        allocate(finance_client, project_id, payment_id, invoice_id=invoice_id, amount="180000.00")
        refused = finance_client.post(
            f"{construction_url(project_id)}/payments/{payment_id}/confirm", json={}
        )
        assert refused.status_code == 403, refused.text

    def test_an_unallocated_payment_cannot_be_confirmed(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
    ) -> None:
        """Unapplied cash leaving is a payment nobody can explain."""
        payment = record_payment(
            finance_client, project_id, active_contract, currency_id, amount="50000.00"
        )
        refused = second_finance_client.post(
            f"{construction_url(project_id)}/payments/{payment.json()['id']}/confirm", json={}
        )
        assert refused.status_code == 422, refused.text

    def test_a_disputed_invoice_cannot_be_paid(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        invoice_id = invoice.json()["id"]
        approve_invoice(second_finance_client, project_id, invoice_id)
        assert (
            finance_client.post(
                f"{construction_url(project_id)}/invoices/{invoice_id}/dispute",
                json={"reason": "Under argument"},
            ).status_code
            == 200
        )

        payment = record_payment(
            finance_client, project_id, active_contract, currency_id, amount="180000.00"
        )
        payment_id = payment.json()["id"]
        allocate(finance_client, project_id, payment_id, invoice_id=invoice_id, amount="180000.00")
        refused = second_finance_client.post(
            f"{construction_url(project_id)}/payments/{payment_id}/confirm", json={}
        )
        assert refused.status_code == 409, refused.text

    def test_a_confirmed_payment_settles_the_liability(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """Given / When / Then: cash out moves, certified cost does not."""
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        invoice_id = invoice.json()["id"]
        approve_invoice(second_finance_client, project_id, invoice_id)
        payment = record_payment(
            finance_client, project_id, active_contract, currency_id, amount="180000.00"
        )
        payment_id = payment.json()["id"]
        allocate(finance_client, project_id, payment_id, invoice_id=invoice_id, amount="180000.00")
        confirmed = second_finance_client.post(
            f"{construction_url(project_id)}/payments/{payment_id}/confirm", json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["payable"]["confirmed_paid"] == "180000.00"
        assert summary["payable"]["invoice_outstanding"] == "0.00"
        assert summary["cost_control"]["certified_to_date"] == "200000.00"

    def test_overpaying_an_invoice_is_refused_at_the_moment_cash_would_leave(
        self,
        finance_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        currency_id: str,
        active_contract: str,
        certified_certificate: str,
    ) -> None:
        """Allocating is bookkeeping on a draft; confirming is the disbursement.

        The ceiling is proved under the invoice's lock at confirmation rather
        than while a recorded payment is still being put together, because that
        is the check two concurrent payments have to be serialised against.
        Allocating 200,000 against an invoice owing 180,000 is therefore
        accepted and then refused, and no cash moves either way.
        """
        invoice = record_invoice(
            finance_client,
            project_id,
            active_contract,
            certificate_id=certified_certificate,
            amount_ex_tax="180000.00",
        )
        invoice_id = invoice.json()["id"]
        approve_invoice(second_finance_client, project_id, invoice_id)
        payment = record_payment(
            finance_client, project_id, active_contract, currency_id, amount="200000.00"
        )
        payment_id = payment.json()["id"]
        allocate(finance_client, project_id, payment_id, invoice_id=invoice_id, amount="200000.00")

        refused = second_finance_client.post(
            f"{construction_url(project_id)}/payments/{payment_id}/confirm", json={}
        )
        assert refused.status_code == 409, refused.text

        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["payable"]["confirmed_paid"] == "0.00"
