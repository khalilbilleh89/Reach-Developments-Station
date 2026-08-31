"""Restructures: replacing a schedule that already has cash against it.

This is the most dangerous operation in the module, and the one with the
sharpest rule: **no unit of cash may vanish and none may appear twice.**

The danger is specific. Activating a replacement version swaps in instalments
with new identifiers, and every allocation already made points at the old ones.
Do that without moving the allocations and a half-collected account comes back
on screen reading as entirely unpaid, with the money still in the ledger and no
longer visible against anything.

So the ordinary payment-plan activation path refuses once cash has been
confirmed, and this path — which carries the allocations across in the same
transaction — is the way through. If a single unit cannot be placed, nothing
happens at all.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.modules.conftest import (
    allocate,
    collection_account,
    collections_url,
    confirm_receipt,
    governing_installments,
    plans_url,
    record_receipt,
    write_schedule,
)

CENT = Decimal("0.01")


def _d(value: str) -> Decimal:
    return Decimal(value)


def _row(sequence: int, fraction: str, due: str) -> dict:
    return {
        "sequence": sequence,
        "label": f"Instalment {sequence}",
        "trigger_type": "fixed_date",
        "contractual_due_date": due,
        "principal_fraction": fraction,
    }


def _open_restructure(
    client: TestClient, project_id: str, sale_id: str, **overrides: object
) -> object:
    body: dict[str, object] = {"reason": "Buyer requested a longer schedule"}
    body.update(overrides)
    return client.post(f"{collections_url(project_id)}/sales/{sale_id}/restructures", json=body)


class TestTheCollectionsBoundary:
    """Given a plan, when cash arrives and somebody tries the ordinary path."""

    def test_before_any_cash_the_ordinary_revision_still_activates(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
    ) -> None:
        """PR-MVP-06's behaviour is unchanged where there is nothing to carry."""
        plan_id, _ = active_plan
        revision = collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions",
            json={"change_reason": "Corrected dates"},
        )
        assert revision.status_code == 201, revision.text
        version_id = revision.json()["version"]["id"]

        assert (
            write_schedule(
                collections_client,
                project_id,
                plan_id,
                version_id,
                [
                    _row(1, "0.250000", "2026-03-01"),
                    _row(2, "0.250000", "2026-06-01"),
                    _row(3, "0.500000", "2026-09-01"),
                ],
            ).status_code
            == 200
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        assert collections_client.post(f"{base}/submit", json={}).status_code == 200
        assert cfo_client.post(f"{base}/approve", json={"reason": "Fine"}).status_code == 200
        activated = cfo_client.post(f"{base}/activate", json={})
        assert activated.status_code == 200, activated.text

    def test_after_cash_the_ordinary_activation_refuses_and_says_how(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
        confirmed_receipt: str,
    ) -> None:
        plan_id, _ = active_plan
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )

        revision = collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions",
            json={"change_reason": "Renegotiated"},
        )
        version_id = revision.json()["version"]["id"]
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                _row(1, "0.250000", "2026-03-01"),
                _row(2, "0.250000", "2026-06-01"),
                _row(3, "0.500000", "2026-09-01"),
            ],
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        collections_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Fine"})

        refused = cfo_client.post(f"{base}/activate", json={})
        assert refused.status_code == 409
        detail = refused.json()["detail"]
        assert "confirmed collection activity" in detail
        assert "Collections restructure" in detail

    def test_the_marker_is_set_by_the_first_confirmed_receipt(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
        recorded_receipt: str,
    ) -> None:
        """A recorded receipt is not cash, so it does not close the boundary."""
        plan_id, _ = active_plan
        before = collections_client.get(f"{plans_url(project_id)}/{plan_id}").json()
        assert before["plan"]["collections_started_at"] is None

        confirm_receipt(finance_client, project_id, recorded_receipt)
        after = collections_client.get(f"{plans_url(project_id)}/{plan_id}").json()
        assert after["plan"]["collections_started_at"] is not None


class TestRaisingARestructure:
    """Given a collected plan, when a restructure is raised."""

    def test_it_opens_a_revision_and_leaves_the_account_alone(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )
        before = collection_account(collections_client, project_id, collecting_sale)

        response = _open_restructure(collections_client, project_id, collecting_sale)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["restructure_number"] == "RST-000001"
        assert body["status"] == "open"
        assert body["source_version_id"] == before["active_payment_plan_version_id"]
        assert body["replacement_version_id"] != body["source_version_id"]

        # The active schedule still governs and the cash is still where it was.
        after = collection_account(collections_client, project_id, collecting_sale)
        assert after["active_payment_plan_version_id"] == before["active_payment_plan_version_id"]
        assert after["allocated_total"] == before["allocated_total"]
        assert after["outstanding_total"] == before["outstanding_total"]

    def test_a_plan_with_no_cash_cannot_be_restructured(
        self, collections_client: TestClient, project_id: str, collecting_sale: str
    ) -> None:
        """There is nothing to carry, so the ordinary revision is the right tool."""
        response = _open_restructure(collections_client, project_id, collecting_sale)
        assert response.status_code == 409
        assert "No cash has been confirmed" in response.json()["detail"]

    def test_only_one_restructure_may_be_open_per_plan(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "100.00"
        )
        assert _open_restructure(collections_client, project_id, collecting_sale).status_code == 201
        second = _open_restructure(collections_client, project_id, collecting_sale)
        assert second.status_code == 409

    def test_an_open_revision_blocks_raising_one(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
        active_plan: tuple[str, str],
    ) -> None:
        plan_id, _ = active_plan
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "100.00"
        )
        collections_client.post(
            f"{plans_url(project_id)}/{plan_id}/versions",
            json={"change_reason": "Unrelated"},
        )
        response = _open_restructure(collections_client, project_id, collecting_sale)
        assert response.status_code == 409
        assert "version in preparation" in response.json()["detail"]

    def test_finance_may_not_raise_a_restructure(
        self,
        finance_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "100.00"
        )
        assert _open_restructure(finance_client, project_id, collecting_sale).status_code == 403


class TestMonetaryConservation:
    """The hard case: cash split across receipts and instalments, then rescheduled.

    Modelled on a real collections mess. One receipt settles the first
    instalment and spills into the second; a later receipt tops the second up
    and leaves change unapplied. The schedule is then replaced with a longer
    one, and all three totals must come out identical to the cent.
    """

    def _arrange(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        sale_id: str,
    ) -> dict[str, Decimal]:
        rows = governing_installments(collections_client, project_id, sale_id)
        i1, i2 = _d(rows[0]["scheduled"]), _d(rows[1]["scheduled"])
        spill = (i2 / 6).quantize(CENT)
        top_up = (i2 / 2).quantize(CENT)
        spare = _d("5000.00")

        first = record_receipt(
            collections_client, project_id, sale_id, str(i1 + spill), receipt_date="2026-01-10"
        ).json()
        confirm_receipt(finance_client, project_id, first["id"])
        assert (
            allocate(
                collections_client, project_id, first["id"], rows[0]["installment_id"], str(i1)
            ).status_code
            == 201
        )
        assert (
            allocate(
                collections_client, project_id, first["id"], rows[1]["installment_id"], str(spill)
            ).status_code
            == 201
        )

        second = record_receipt(
            collections_client, project_id, sale_id, str(top_up + spare), receipt_date="2026-02-10"
        ).json()
        confirm_receipt(finance_client, project_id, second["id"])
        assert (
            allocate(
                collections_client, project_id, second["id"], rows[1]["installment_id"], str(top_up)
            ).status_code
            == 201
        )
        # ``spare`` is deliberately left unapplied and must stay that way.

        return {
            "receipts": i1 + spill + top_up + spare,
            "allocated": i1 + spill + top_up,
            "unapplied": spare,
        }

    def _replace_and_approve(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        plan_id: str,
        version_id: str,
    ) -> None:
        assert (
            write_schedule(
                collections_client,
                project_id,
                plan_id,
                version_id,
                [
                    _row(1, "0.100000", "2026-03-01"),
                    _row(2, "0.150000", "2026-06-01"),
                    _row(3, "0.250000", "2026-09-01"),
                    _row(4, "0.500000", "2026-12-01"),
                ],
            ).status_code
            == 200
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        assert collections_client.post(f"{base}/submit", json={}).status_code == 200
        assert (
            cfo_client.post(
                f"{base}/approve", json={"reason": "Restructure sanctioned"}
            ).status_code
            == 200
        )

    def test_every_unit_of_cash_survives_the_restructure(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
    ) -> None:
        plan_id, _ = active_plan
        expected = self._arrange(collections_client, finance_client, project_id, collecting_sale)
        before = collection_account(collections_client, project_id, collecting_sale)
        assert _d(before["confirmed_receipts_total"]) == expected["receipts"]
        assert _d(before["allocated_total"]) == expected["allocated"]
        assert _d(before["unapplied_cash"]) == expected["unapplied"]

        restructure = _open_restructure(collections_client, project_id, collecting_sale).json()
        self._replace_and_approve(
            collections_client,
            cfo_client,
            project_id,
            plan_id,
            restructure["replacement_version_id"],
        )

        preview = collections_client.get(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/preview"
        )
        assert preview.status_code == 200, preview.text
        plan = preview.json()
        assert plan["ready_to_apply"] is True
        assert plan["blockers"] == []
        assert _d(plan["carried_total"]) == expected["allocated"]
        assert _d(plan["unapplied_total"]) == expected["unapplied"]

        applied = collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/apply", json={}
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["restructure"]["status"] == "applied"

        after = collection_account(collections_client, project_id, collecting_sale)
        # The three figures that must not move.
        assert _d(after["confirmed_receipts_total"]) == expected["receipts"]
        assert _d(after["allocated_total"]) == expected["allocated"]
        assert _d(after["unapplied_cash"]) == expected["unapplied"]
        # And the schedule genuinely changed underneath them.
        assert after["active_payment_plan_version_id"] == restructure["replacement_version_id"]
        assert after["installments_total"] == 4

    def test_the_old_allocations_are_superseded_not_deleted(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
    ) -> None:
        plan_id, _ = active_plan
        self._arrange(collections_client, finance_client, project_id, collecting_sale)
        restructure = _open_restructure(collections_client, project_id, collecting_sale).json()
        self._replace_and_approve(
            collections_client,
            cfo_client,
            project_id,
            plan_id,
            restructure["replacement_version_id"],
        )
        collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/apply", json={}
        )

        receipts = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/receipts"
        ).json()
        statuses: list[str] = []
        for receipt in receipts:
            statuses.extend(a["status"] for a in receipt["allocations"])
        assert "superseded" in statuses
        assert "active" in statuses
        assert "reversed" not in statuses

        superseded = [
            a for receipt in receipts for a in receipt["allocations"] if a["status"] == "superseded"
        ]
        assert all(a["superseded_by_restructure_id"] == restructure["id"] for a in superseded)

    def test_unapplied_cash_is_not_swept_up_by_the_restructure(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
    ) -> None:
        """A restructure moves cash somebody applied. It never applies more."""
        plan_id, _ = active_plan
        expected = self._arrange(collections_client, finance_client, project_id, collecting_sale)
        restructure = _open_restructure(collections_client, project_id, collecting_sale).json()
        self._replace_and_approve(
            collections_client,
            cfo_client,
            project_id,
            plan_id,
            restructure["replacement_version_id"],
        )
        collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/apply", json={}
        )
        after = collection_account(collections_client, project_id, collecting_sale)
        assert _d(after["unapplied_cash"]) == expected["unapplied"]


class TestApplyRefusals:
    """Given a restructure that is not ready, when somebody tries to apply it."""

    def _raise_one(
        self,
        collections_client: TestClient,
        project_id: str,
        sale_id: str,
        confirmed_receipt: str,
    ) -> dict:
        rows = governing_installments(collections_client, project_id, sale_id)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )
        return _open_restructure(collections_client, project_id, sale_id).json()

    def test_an_unapproved_replacement_cannot_be_applied(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        restructure = self._raise_one(
            collections_client, project_id, collecting_sale, confirmed_receipt
        )
        response = collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/apply", json={}
        )
        assert response.status_code == 409
        assert "not been approved" in response.json()["detail"]

    def test_the_preview_names_the_blocker_rather_than_failing(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        restructure = self._raise_one(
            collections_client, project_id, collecting_sale, confirmed_receipt
        )
        preview = collections_client.get(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/preview"
        ).json()
        assert preview["ready_to_apply"] is False
        assert any("approved" in b for b in preview["blockers"])
        # The plan is still computed, so the operator can see what would happen.
        assert preview["lines"]

    def test_a_failed_apply_moves_nothing_at_all(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
        active_plan: tuple[str, str],
    ) -> None:
        """Atomicity, proved at the point the carry-forward has already been written.

        The replacement is approved but dated in the future, so activation
        refuses *after* the allocations have been superseded and re-created
        inside the transaction. Everything must roll back together: the old
        version still governs, its allocations are still active, and the
        restructure is still open.
        """
        plan_id, _ = active_plan
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )
        before = collection_account(collections_client, project_id, collecting_sale)

        restructure = _open_restructure(
            collections_client, project_id, collecting_sale, effective_date="2099-01-01"
        ).json()
        version_id = restructure["replacement_version_id"]
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                _row(1, "0.100000", "2026-03-01"),
                _row(2, "0.150000", "2026-06-01"),
                _row(3, "0.250000", "2026-09-01"),
                _row(4, "0.500000", "2026-12-01"),
            ],
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        collections_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Sanctioned, effective later"})

        response = collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/apply", json={}
        )
        assert response.status_code == 409
        assert "takes effect on 2099-01-01" in response.json()["detail"]

        after = collection_account(collections_client, project_id, collecting_sale)
        assert after["active_payment_plan_version_id"] == before["active_payment_plan_version_id"]
        assert after["allocated_total"] == before["allocated_total"]
        assert after["unapplied_cash"] == before["unapplied_cash"]
        assert after["installments_total"] == before["installments_total"]

        still_open = collections_client.get(
            f"{collections_url(project_id)}/sales/{collecting_sale}/restructures"
        ).json()
        assert [r["status"] for r in still_open] == ["open"]

        receipt = collections_client.get(
            f"{collections_url(project_id)}/receipts/{confirmed_receipt}"
        ).json()
        assert [a["status"] for a in receipt["allocations"]] == ["active"]

    def test_an_applied_restructure_cannot_be_applied_twice(
        self,
        collections_client: TestClient,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        active_plan: tuple[str, str],
        confirmed_receipt: str,
    ) -> None:
        plan_id, _ = active_plan
        restructure = self._raise_one(
            collections_client, project_id, collecting_sale, confirmed_receipt
        )
        version_id = restructure["replacement_version_id"]
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                _row(1, "0.300000", "2026-03-01"),
                _row(2, "0.300000", "2026-06-01"),
                _row(3, "0.400000", "2026-09-01"),
            ],
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        collections_client.post(f"{base}/submit", json={})
        cfo_client.post(f"{base}/approve", json={"reason": "Fine"})
        url = f"{collections_url(project_id)}/restructures/{restructure['id']}/apply"
        assert collections_client.post(url, json={}).status_code == 200
        assert collections_client.post(url, json={}).status_code == 409


class TestAbandoning:
    """Given a refused replacement, when the restructure has to be closed."""

    def test_a_restructure_can_be_abandoned_and_another_raised(
        self,
        collections_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
        active_plan: tuple[str, str],
    ) -> None:
        """Without this, one CFO refusal would block the plan for ever.

        PR-MVP-06 makes a rejected version terminal, so a restructure whose
        replacement was refused can never be applied. It has to be closable.
        """
        plan_id, _ = active_plan
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )
        restructure = _open_restructure(collections_client, project_id, collecting_sale).json()
        version_id = restructure["replacement_version_id"]
        write_schedule(
            collections_client,
            project_id,
            plan_id,
            version_id,
            [
                _row(1, "0.300000", "2026-03-01"),
                _row(2, "0.300000", "2026-06-01"),
                _row(3, "0.400000", "2026-09-01"),
            ],
        )
        base = f"{plans_url(project_id)}/{plan_id}/versions/{version_id}"
        collections_client.post(f"{base}/submit", json={})
        rejected = cfo_client.post(f"{base}/reject", json={"reason": "Terms unacceptable"})
        assert rejected.status_code == 200, rejected.text

        abandoned = collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/abandon",
            json={"reason": "Replacement schedule was refused by the CFO"},
        )
        assert abandoned.status_code == 200, abandoned.text
        assert abandoned.json()["status"] == "abandoned"

        # The plan is workable again.
        assert _open_restructure(collections_client, project_id, collecting_sale).status_code == 201

    def test_abandoning_moves_no_money(
        self,
        collections_client: TestClient,
        project_id: str,
        collecting_sale: str,
        confirmed_receipt: str,
    ) -> None:
        rows = governing_installments(collections_client, project_id, collecting_sale)
        allocate(
            collections_client, project_id, confirmed_receipt, rows[0]["installment_id"], "10000.00"
        )
        before = collection_account(collections_client, project_id, collecting_sale)
        restructure = _open_restructure(collections_client, project_id, collecting_sale).json()
        collections_client.post(
            f"{collections_url(project_id)}/restructures/{restructure['id']}/abandon",
            json={"reason": "Not proceeding"},
        )
        after = collection_account(collections_client, project_id, collecting_sale)
        assert after["allocated_total"] == before["allocated_total"]
        assert after["active_payment_plan_version_id"] == before["active_payment_plan_version_id"]
