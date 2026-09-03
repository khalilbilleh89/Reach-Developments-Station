"""Who may see what the build costs, and what a partial view must never become.

Five separations, and each one is a specific leak if it is missing. The reading
list is shorter than the project's because a unit's build cost is not a
salesperson's business. The System Administrator reads and signs nothing. A
phase-scoped reader is refused a project total rather than shown a filtered one.
A record of another project answers as absent, not as forbidden.

And the other half of the phase rule, which is the one with teeth: a technical
record that genuinely belongs to a phase stays available to the people holding
that phase, and *only* to them. Milestones are where that matters most, because
certifying one makes buyers' instalments fall due — so a Phase A engineer
reaching a Phase B milestone by identifier is not a display bug, it is an
unauthorised financial act one request away.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.access.models import User
from tests.factories import client_for, make_user
from tests.modules.conftest import (
    PROJECTS,
    construction_url,
    create_budget,
    create_milestone,
    grant_access,
    inventory_url,
    project_payload,
)

#: Every whole-project financial surface. A phase-scoped reader gets none.
PROJECT_TOTALS = (
    "/summary",
    "/reconciliation",
    "/budgets",
    "/contracts",
    "/variations",
    "/certificates",
    "/invoices",
    "/payments",
    "/forecasts",
)


@pytest.fixture
def scoped_engineer(db: Session, admin_client: TestClient, project_id: str, phase_id: str) -> User:
    """A Design / Engineering user granted one phase rather than the project."""
    user = make_user(db, email="scoped@example.com", roles=("design_engineering",))
    grant_access(admin_client, project_id, user)
    # Membership alone sees every phase. Narrowing is a second, explicit act,
    # and without it this fixture would build a full-access reader and the tests
    # below would pass for the wrong reason.
    narrowed = admin_client.patch(
        f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
        json={"phase_scope": "selected"},
    )
    assert narrowed.status_code == 200, narrowed.text
    granted = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}/phases/{phase_id}")
    assert granted.status_code in {200, 201}, granted.text
    return user


class TestTheReadingList:
    @pytest.mark.parametrize(
        "role",
        ["sales_advisor", "sales_operations", "legal", "collections"],
    )
    def test_a_commercial_role_may_not_read_construction(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        active_budget: str,
        role: str,
    ) -> None:
        """Seeing a unit is not a reason to see what building it cost."""
        user = make_user(db, email=f"{role}@construction.example", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        refused = client.get(f"{construction_url(project_id)}/summary")
        assert refused.status_code == 403, refused.text

    @pytest.mark.parametrize(
        "role",
        ["project_manager", "design_engineering", "finance", "approver_cfo", "auditor"],
    )
    def test_a_delivery_or_finance_role_may_read_construction(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        active_budget: str,
        role: str,
    ) -> None:
        user = make_user(db, email=f"{role}@reader.example", roles=(role,))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        allowed = client.get(f"{construction_url(project_id)}/summary")
        assert allowed.status_code == 200, allowed.text

    def test_design_engineering_reads_construction_and_not_unit_economics(
        self,
        engineer_client: TestClient,
        project_id: str,
        active_budget: str,
    ) -> None:
        """The difference between the two modules, stated as a test.

        What the build costs the developer is information the people running the
        build need. What margin a unit earns is not.
        """
        from tests.modules.conftest import economics_url

        assert engineer_client.get(f"{construction_url(project_id)}/summary").status_code == 200
        refused = engineer_client.get(f"{economics_url(project_id)}/allocation-versions")
        assert refused.status_code == 403, refused.text


class TestTheAdministratorSignsNothing:
    def test_an_administrator_reads_everything_and_approves_nothing(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        assert admin_client.get(f"{construction_url(project_id)}/summary").status_code == 200

        version_id = create_budget(
            finance_client,
            project_id,
            effective_date="2026-12-01",
            change_reason="Revision",
        ).json()["id"]
        refused = admin_client.put(
            f"{construction_url(project_id)}/budgets/{version_id}/lines",
            json={"cost_code_id": cost_codes["hard"], "approved_budget_amount": "1.00"},
        )
        assert refused.status_code == 403, refused.text


class TestAPartialViewIsRefusedNotFiltered:
    def test_a_phase_scoped_reader_is_refused_every_project_total(
        self,
        admin_client: TestClient,
        scoped_engineer: User,
        project_id: str,
        active_budget: str,
    ) -> None:
        """A filtered total is neither the project's nor the reader's own."""
        client = client_for(scoped_engineer.email)
        for path in PROJECT_TOTALS:
            refused = client.get(f"{construction_url(project_id)}{path}")
            assert refused.status_code == 403, f"{path}: {refused.text}"

    def test_a_phase_scoped_reader_keeps_the_technical_record(
        self,
        admin_client: TestClient,
        scoped_engineer: User,
        project_id: str,
        active_budget: str,
    ) -> None:
        """Milestones and cost codes genuinely belong to a phase, and stay."""
        client = client_for(scoped_engineer.email)
        assert client.get(f"{construction_url(project_id)}/milestones").status_code == 200
        assert client.get(f"{construction_url(project_id)}/cost-codes").status_code == 200


class TestAnotherProjectAnswersAsAbsent:
    def test_a_contract_of_another_project_is_not_found(
        self,
        admin_client: TestClient,
        finance_client: TestClient,
        project_id: str,
        country_pack_id: str,
        currency_id: str,
        active_contract: str,
    ) -> None:
        """A 403 would confirm the identifier names something real."""
        other = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code="OTHER-03", name="Second development"
            ),
        )
        assert other.status_code == 201, other.text
        other_id = other.json()["id"]

        answer = admin_client.get(f"{construction_url(other_id)}/contracts/{active_contract}")
        assert answer.status_code == 404, answer.text

    def test_a_non_member_sees_no_project_at_all(
        self, db: Session, project_id: str, active_budget: str
    ) -> None:
        outsider = make_user(db, email="outsider@example.com", roles=("finance",))
        client = client_for(outsider.email)
        answer = client.get(f"{construction_url(project_id)}/summary")
        assert answer.status_code == 404, answer.text


@pytest.fixture
def second_phase(admin_client: TestClient, project_id: str, phase_id: str) -> str:
    """A phase the scoped engineer is deliberately not given."""
    response = admin_client.post(
        f"{inventory_url(project_id)}/phases",
        json={"code": "PHASE-2", "name": "Phase 2", "sequence": 2},
    )
    assert response.status_code == 201, response.text
    identifier: str = response.json()["id"]
    return identifier


@pytest.fixture
def phase_milestones(
    manager_member_client: TestClient,
    project_id: str,
    phase_id: str,
    second_phase: str,
) -> dict[str, str]:
    """One milestone in each phase, and one belonging to the whole project.

    Written by a whole-project Project Manager, which is the only actor who may
    author the unscoped one — the register a phase-scoped engineer then reads
    has to separate them without any of the three having been created
    differently.
    """
    milestones: dict[str, str] = {}
    for key, code, scope in (
        ("a", "PHASE-A-TOP", {"phase_id": phase_id}),
        ("b", "PHASE-B-TOP", {"phase_id": second_phase}),
        ("project", "PRACTICAL-COMPLETION", {}),
    ):
        created = create_milestone(
            manager_member_client,
            project_id,
            code=code,
            name=f"{code} reached",
            **scope,
        )
        assert created.status_code == 201, created.text
        milestones[key] = created.json()["id"]
    return milestones


class TestAPhaseScopedActorReachesOnlyTheirOwnMilestones:
    """The register narrows in SQL. Nothing here is hidden by the browser."""

    def test_the_register_carries_their_phase_and_no_other(
        self,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        client = client_for(scoped_engineer.email)
        listed = client.get(f"{construction_url(project_id)}/milestones")
        assert listed.status_code == 200, listed.text
        codes = {row["code"] for row in listed.json()}
        assert codes == {"PHASE-A-TOP"}

    def test_a_hidden_milestone_answers_as_absent(
        self,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        """404 and not 403: a refusal that confirms the identifier is a leak."""
        client = client_for(scoped_engineer.email)
        answer = client.get(f"{construction_url(project_id)}/milestones/{phase_milestones['b']}")
        assert answer.status_code == 404, answer.text

    @pytest.mark.parametrize(
        ("method", "suffix", "payload"),
        [
            ("patch", "", {"name": "Renamed from outside the phase"}),
            ("post", "/achieve", {"achieved_date": "2026-03-01"}),
            ("post", "/certify", {"certified_date": "2026-03-02"}),
            ("post", "/cancel", {"reason": "Not my phase"}),
        ],
    )
    def test_every_mutation_of_a_hidden_milestone_is_refused(
        self,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
        method: str,
        suffix: str,
        payload: dict[str, object],
    ) -> None:
        """The retrieval path is the gate, so each mutation inherits it.

        Design / Engineering holds both the technical and the certifier role, so
        none of these is refused for lacking a role. What refuses them is that
        the milestone is not theirs to reach.
        """
        client = client_for(scoped_engineer.email)
        url = f"{construction_url(project_id)}/milestones/{phase_milestones['b']}{suffix}"
        refused = getattr(client, method)(url, json=payload)
        assert refused.status_code == 404, refused.text

    def test_certifying_a_hidden_milestone_moves_no_schedule(
        self,
        manager_member_client: TestClient,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        """The refusal has to leave the record untouched, not merely answer 404."""
        client = client_for(scoped_engineer.email)
        refused = client.post(
            f"{construction_url(project_id)}/milestones/{phase_milestones['b']}/certify",
            json={"certified_date": "2026-03-02"},
        )
        assert refused.status_code == 404, refused.text

        still = manager_member_client.get(
            f"{construction_url(project_id)}/milestones/{phase_milestones['b']}"
        )
        assert still.status_code == 200, still.text
        assert still.json()["status"] == "planned"
        assert still.json()["certified_date"] is None

    def test_a_dependency_may_not_be_hung_on_a_hidden_milestone(
        self,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        """Supplying the identifier is the attack, and it answers the same way."""
        client = client_for(scoped_engineer.email)
        refused = client.put(
            f"{construction_url(project_id)}/milestones/{phase_milestones['a']}/dependencies",
            json={"depends_on_milestone_id": phase_milestones["b"]},
        )
        assert refused.status_code == 404, refused.text

    def test_a_whole_project_milestone_is_not_theirs_either(
        self,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        """Scoped to no phase is scoped to all of them, which is the wider claim."""
        client = client_for(scoped_engineer.email)
        refused = client.post(
            f"{construction_url(project_id)}/milestones/{phase_milestones['project']}/certify",
            json={"certified_date": "2026-03-02"},
        )
        assert refused.status_code == 404, refused.text

    def test_they_may_not_author_a_whole_project_milestone(
        self, scoped_engineer: User, project_id: str, phase_id: str
    ) -> None:
        """403, because there is no record here whose existence needs protecting."""
        client = client_for(scoped_engineer.email)
        refused = create_milestone(client, project_id, code="PC-01", name="Practical completion")
        assert refused.status_code == 403, refused.text

        scoped = create_milestone(
            client, project_id, code="PA-02", name="Second floor", phase_id=phase_id
        )
        assert scoped.status_code == 201, scoped.text

    def test_they_may_not_widen_their_own_milestone_into_one(
        self, scoped_engineer: User, project_id: str, phase_id: str
    ) -> None:
        """Clearing the phase is the same act by another route."""
        client = client_for(scoped_engineer.email)
        milestone_id = create_milestone(
            client, project_id, code="PA-03", name="Third floor", phase_id=phase_id
        ).json()["id"]
        refused = client.patch(
            f"{construction_url(project_id)}/milestones/{milestone_id}",
            json={"phase_id": None},
        )
        assert refused.status_code == 403, refused.text

    def test_a_whole_project_actor_authors_one_normally(
        self, manager_member_client: TestClient, project_id: str
    ) -> None:
        """The refusal is about scope, not about the record being forbidden."""
        created = create_milestone(
            manager_member_client, project_id, code="PC-02", name="Practical completion"
        )
        assert created.status_code == 201, created.text
        assert created.json()["phase_id"] is None

    def test_a_hidden_dependency_is_not_reported_on_a_visible_milestone(
        self,
        manager_member_client: TestClient,
        scoped_engineer: User,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        """A whole-project planner may record the edge; this reader is not shown it.

        Handing back the identifier would tell a Phase A engineer that a record
        they cannot open exists, and give them the handle for it.
        """
        linked = manager_member_client.put(
            f"{construction_url(project_id)}/milestones/{phase_milestones['a']}/dependencies",
            json={"depends_on_milestone_id": phase_milestones["b"]},
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()["depends_on"] == [phase_milestones["b"]]

        client = client_for(scoped_engineer.email)
        seen = client.get(f"{construction_url(project_id)}/milestones/{phase_milestones['a']}")
        assert seen.status_code == 200, seen.text
        assert seen.json()["depends_on"] == []

    def test_an_identifier_of_nothing_answers_the_same_way(
        self, scoped_engineer: User, project_id: str, phase_milestones: dict[str, str]
    ) -> None:
        """A hidden record and a missing one must be indistinguishable."""
        client = client_for(scoped_engineer.email)
        missing = client.get(f"{construction_url(project_id)}/milestones/{uuid.uuid4()}")
        assert missing.status_code == 404, missing.text


class TestTheTriggerOptionsRespectTheSameScope:
    """The one route a payment plan user may reach, narrowed the same way."""

    @pytest.fixture
    def scoped_planner(
        self, db: Session, admin_client: TestClient, project_id: str, phase_id: str
    ) -> User:
        """Sales Operations, holding one phase of the project and no more."""
        user = make_user(db, email="scoped.plans@example.com", roles=("sales_operations",))
        grant_access(admin_client, project_id, user)
        narrowed = admin_client.patch(
            f"{PROJECTS}/{project_id}/access/{user.id}/phase-scope",
            json={"phase_scope": "selected"},
        )
        assert narrowed.status_code == 200, narrowed.text
        granted = admin_client.put(f"{PROJECTS}/{project_id}/access/{user.id}/phases/{phase_id}")
        assert granted.status_code in {200, 201}, granted.text
        return user

    def test_a_phase_scoped_planner_is_offered_only_their_phase(
        self, scoped_planner: User, project_id: str, phase_milestones: dict[str, str]
    ) -> None:
        """Not being able to read construction is not what limits this caller.

        Holding one phase is. Milestone names and programme dates for a phase
        somebody was deliberately not given are the same disclosure whether they
        arrive through the register or through the narrow schema a plan builder
        is allowed.
        """
        client = client_for(scoped_planner.email)
        options = client.get(f"{construction_url(project_id)}/milestone-trigger-options")
        assert options.status_code == 200, options.text
        codes = {row["code"] for row in options.json()}
        assert codes == {"PHASE-A-TOP"}
        assert all("amount" not in row for row in options.json())

    def test_a_whole_project_planner_is_offered_all_of_them(
        self,
        db: Session,
        admin_client: TestClient,
        project_id: str,
        phase_milestones: dict[str, str],
    ) -> None:
        user = make_user(db, email="plans@example.com", roles=("sales_operations",))
        grant_access(admin_client, project_id, user)
        client = client_for(user.email)
        options = client.get(f"{construction_url(project_id)}/milestone-trigger-options")
        assert options.status_code == 200, options.text
        codes = {row["code"] for row in options.json()}
        assert codes == {"PHASE-A-TOP", "PHASE-B-TOP", "PRACTICAL-COMPLETION"}


class TestNothingIsDeletable:
    def test_construction_exposes_no_delete_route(self) -> None:
        """Governed history is superseded, reversed or voided. Never removed."""
        from app.main import create_app

        paths = create_app().openapi()["paths"]
        deletes = [
            path
            for path, methods in paths.items()
            if "/construction" in path and "delete" in methods
        ]
        assert deletes == []
