"""Milestones: the boundary between site reporting and a buyer's money.

The gap between *achieved* and *certified* is the whole control. Somebody on
site saying a floor is complete is information. Certification is the formal act
a buyer's contract makes their payment depend on, and it is the only one that
reaches a payment plan.
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from tests.modules.conftest import construction_url, create_milestone


class TestAchievedIsNotCertified:
    def test_achieving_a_milestone_triggers_nothing(
        self,
        manager_member_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """Given / When / Then: site reports completion; no schedule moves."""
        created = create_milestone(manager_member_client, project_id)
        assert created.status_code == 201, created.text
        milestone_id = created.json()["id"]

        achieved = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone_id}/achieve",
            json={"achieved_date": "2026-03-01", "evidence_reference": "SITE-REP-14"},
        )
        assert achieved.status_code == 200, achieved.text
        body = achieved.json()
        assert body["status"] == "achieved"
        assert body["actual_achieved_date"] == "2026-03-01"
        assert body["certified_date"] is None

    def test_certifying_a_milestone_reports_what_it_triggered(
        self,
        manager_member_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """With no plan waiting on it, the answer is zero — stated, not implied."""
        milestone_id = create_milestone(manager_member_client, project_id).json()["id"]
        certified = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone_id}/certify",
            json={"certified_date": "2026-03-02"},
        )
        assert certified.status_code == 200, certified.text
        body = certified.json()
        assert body["milestone"]["status"] == "certified"
        assert body["milestone"]["certified_date"] == "2026-03-02"
        assert body["triggered_installment_count"] == 0
        assert body["triggered_plan_count"] == 0


class TestCertificationIsNotMoved:
    def test_re_certifying_on_the_same_date_is_a_no_op(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """A retried request is not a failure."""
        milestone_id = create_milestone(manager_member_client, project_id).json()["id"]
        url = f"{construction_url(project_id)}/milestones/{milestone_id}/certify"
        first = manager_member_client.post(url, json={"certified_date": "2026-03-02"})
        assert first.status_code == 200, first.text
        again = manager_member_client.post(url, json={"certified_date": "2026-03-02"})
        assert again.status_code == 200, again.text
        assert again.json()["triggered_installment_count"] == 0

    def test_re_certifying_on_a_different_date_is_refused(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """A buyer's instalment may already be due on the first date."""
        milestone_id = create_milestone(manager_member_client, project_id).json()["id"]
        url = f"{construction_url(project_id)}/milestones/{milestone_id}/certify"
        assert (
            manager_member_client.post(url, json={"certified_date": "2026-03-02"}).status_code
            == 200
        )
        refused = manager_member_client.post(url, json={"certified_date": "2026-04-02"})
        assert refused.status_code == 409, refused.text

    def test_a_cancelled_milestone_cannot_be_certified(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        milestone_id = create_milestone(manager_member_client, project_id).json()["id"]
        cancelled = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone_id}/cancel",
            json={"reason": "Scope removed from the programme"},
        )
        assert cancelled.status_code == 200, cancelled.text
        refused = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone_id}/certify",
            json={"certified_date": "2026-03-02"},
        )
        assert refused.status_code == 409, refused.text


class TestTriggerOptions:
    def test_the_selector_names_milestones_and_states_no_money(
        self,
        manager_member_client: TestClient,
        collections_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """A payment-plan author picks a code, and sees no construction cost.

        The selector exists so a plan stores ``milestone.code`` rather than a
        typed string that nothing validates. It is deliberately the one
        construction route a Collections user may read, and it carries no
        amount, no contract and no vendor.
        """
        assert create_milestone(manager_member_client, project_id).status_code == 201
        options = collections_client.get(
            f"{construction_url(project_id)}/milestone-trigger-options"
        )
        assert options.status_code == 200, options.text
        rows = options.json()
        assert [row["code"] for row in rows] == ["FOUNDATION"]
        assert set(rows[0]) == {
            "code",
            "name",
            "scope_label",
            "planned_date",
            "forecast_date",
            "is_certified",
            "certified_date",
        }

    def test_a_collections_user_may_read_nothing_else_of_construction(
        self, collections_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        refused = collections_client.get(f"{construction_url(project_id)}/summary")
        assert refused.status_code == 403, refused.text


class TestScopeAndDates:
    def test_a_milestone_may_name_a_phase_it_belongs_to(
        self,
        manager_member_client: TestClient,
        project_id: str,
        phase_id: str,
        active_budget: str,
    ) -> None:
        created = create_milestone(
            manager_member_client,
            project_id,
            code="PHASE-TOPOUT",
            name="Phase A top out",
            phase_id=phase_id,
            planned_date="2026-06-30",
        )
        assert created.status_code == 201, created.text
        assert created.json()["phase_id"] == phase_id
        assert created.json()["scope_label"] is not None

    def test_a_milestone_cannot_name_a_phase_of_another_project(
        self,
        manager_member_client: TestClient,
        admin_client: TestClient,
        project_id: str,
        country_pack_id: str,
        currency_id: str,
        active_budget: str,
    ) -> None:
        """PR-MVP-09 foundation fix: scope identifiers are validated, not stored."""
        from tests.modules.conftest import PROJECTS, project_payload

        other = admin_client.post(
            PROJECTS,
            json=project_payload(country_pack_id, currency_id, code="OTHER-02", name="Elsewhere"),
        )
        assert other.status_code == 201, other.text
        other_id = other.json()["id"]
        assert (
            admin_client.patch(
                f"{PROJECTS}/{other_id}", json={"status": "predevelopment"}
            ).status_code
            == 200
        )
        phase = admin_client.post(
            f"{PROJECTS}/{other_id}/inventory/phases",
            json={"code": "PH-X", "name": "Foreign phase", "sequence": 1},
        )
        assert phase.status_code == 201, phase.text

        refused = create_milestone(
            manager_member_client,
            project_id,
            code="FOREIGN",
            name="Wrong project's phase",
            phase_id=phase.json()["id"],
        )
        assert refused.status_code in {404, 422}, refused.text

    def test_delay_is_measured_against_the_planned_date(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        created = create_milestone(
            manager_member_client,
            project_id,
            code="LATE",
            name="Late milestone",
            planned_date="2026-01-01",
        )
        milestone_id = created.json()["id"]
        achieved = manager_member_client.post(
            f"{construction_url(project_id)}/milestones/{milestone_id}/achieve",
            json={"achieved_date": "2026-01-11"},
        )
        assert achieved.status_code == 200, achieved.text
        assert achieved.json()["delay_days"] == 10

    def test_an_unachieved_milestone_past_its_planned_date_reads_as_late(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        created = create_milestone(
            manager_member_client,
            project_id,
            code="OVERDUE",
            name="Overdue milestone",
            planned_date="2020-01-01",
        )
        assert created.status_code == 201, created.text
        summary = manager_member_client.get(f"{construction_url(project_id)}/summary").json()
        assert summary["controls"]["late_milestones"] >= 1


class TestDependencies:
    def test_a_milestone_may_depend_on_another(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        first = create_milestone(manager_member_client, project_id).json()["id"]
        second = create_milestone(
            manager_member_client, project_id, code="SUPER", name="Superstructure"
        ).json()["id"]
        linked = manager_member_client.put(
            f"{construction_url(project_id)}/milestones/{second}/dependencies",
            json={"depends_on_milestone_id": first},
        )
        assert linked.status_code == 200, linked.text
        assert first in linked.json()["depends_on"]

    def test_a_milestone_cannot_depend_on_itself(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        milestone_id = create_milestone(manager_member_client, project_id).json()["id"]
        refused = manager_member_client.put(
            f"{construction_url(project_id)}/milestones/{milestone_id}/dependencies",
            json={"depends_on_milestone_id": milestone_id},
        )
        assert refused.status_code == 422, refused.text


class TestForecastDatesAreNotHistory:
    def test_a_certified_milestone_keeps_its_certified_date(
        self, manager_member_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """Given / When / Then: the record of when it happened is not editable."""
        milestone_id = create_milestone(manager_member_client, project_id).json()["id"]
        assert (
            manager_member_client.post(
                f"{construction_url(project_id)}/milestones/{milestone_id}/certify",
                json={"certified_date": date.today().isoformat()},
            ).status_code
            == 200
        )
        read = manager_member_client.get(
            f"{construction_url(project_id)}/milestones/{milestone_id}"
        ).json()
        assert read["certified_date"] == date.today().isoformat()
        assert read["status"] == "certified"
