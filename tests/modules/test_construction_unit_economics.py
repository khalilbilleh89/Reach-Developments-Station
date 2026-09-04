"""The one place construction reaches unit economics, and the direction it runs.

Unit economics *consumes* construction's hard-cost estimate at completion
through a named contract. Construction never writes a cost pool, never reads an
allocation, and never learns what a unit earns. The properties proved here are
the ones that make that safe: the amount is derived and not typed, its
provenance is recorded, hard cost has one source, and a later forecast never
rewrites a basis somebody already sold units against.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.modules.conftest import (
    add_pool,
    at,
    backdate,
    certify,
    construction_url,
    cover_required_pools,
    create_certificate,
    create_forecast,
    create_version,
    economics_url,
    govern_forecast,
    set_certificate_line,
    set_forecast_line,
)


def active_forecast_of(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    *,
    hard: str,
) -> str:
    """Put a forecast in force with ``hard`` remaining on the hard cost code."""
    version_id = create_forecast(finance_client, project_id).json()["id"]
    for category, amount in (
        ("hard", hard),
        ("soft", "0.00"),
        ("contingency", "0.00"),
        ("other", "0.00"),
    ):
        response = set_forecast_line(
            finance_client,
            project_id,
            version_id,
            cost_code_id=cost_codes[category],
            forecast_remaining_amount_ex_tax=amount,
        )
        assert response.status_code == 200, response.text
    governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
    assert governed.status_code == 200, governed.text
    return version_id


def active_forecast_as_at(
    finance_client: TestClient,
    cfo_client: TestClient,
    project_id: str,
    cost_codes: dict[str, str],
    *,
    hard: str,
    as_of: date,
) -> str:
    """The same forecast, taken as at a stated cutoff rather than today.

    A historical cutoff is what makes a reversal *after* it something other than
    an edit to the basis, so the reversal tests need one they can put a later
    event beyond.
    """
    version_id = create_forecast(finance_client, project_id, as_of_date=as_of.isoformat()).json()[
        "id"
    ]
    for category, amount in (
        ("hard", hard),
        ("soft", "0.00"),
        ("contingency", "0.00"),
        ("other", "0.00"),
    ):
        response = set_forecast_line(
            finance_client,
            project_id,
            version_id,
            cost_code_id=cost_codes[category],
            forecast_remaining_amount_ex_tax=amount,
        )
        assert response.status_code == 200, response.text
    governed = govern_forecast(finance_client, cfo_client, project_id, version_id)
    assert governed.status_code == 200, governed.text
    return version_id


def pools_of(client: TestClient, project_id: str, version_id: str) -> list[dict[str, object]]:
    response = client.get(f"{economics_url(project_id)}/allocation-versions/{version_id}")
    assert response.status_code == 200, response.text
    return response.json()["pools"]


class TestTheAmountIsDerived:
    def test_a_construction_pool_takes_the_forecasts_estimate_at_completion(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
        unit_id: str,
    ) -> None:
        """Given / When / Then: the pool's amount is the forecast's, not a typed one."""
        forecast_id = active_forecast_of(
            finance_client, cfo_client, project_id, cost_codes, hard="7500000.00"
        )
        version_id = create_version(finance_client, project_id)
        created = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-CX",
            category="hard",
            source_kind="construction_forecast",
            amount="1.00",
        )
        assert created.status_code == 201, created.text
        assert created.json()["amount"] == "7500000.00"
        assert created.json()["source_construction_forecast_version_id"] == forecast_id

    def test_a_construction_pool_cannot_be_retyped(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        pool_id = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-CX",
            category="hard",
            source_kind="construction_forecast",
            amount=None,
        ).json()["id"]

        refused = finance_client.patch(
            f"{economics_url(project_id)}/allocation-versions/{version_id}/pools/{pool_id}",
            json={"amount": "1.00"},
        )
        assert refused.status_code == 409, refused.text

    def test_without_an_active_forecast_there_is_no_estimate_to_allocate(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        """Zero would be a hard cost of nothing that reconciles perfectly."""
        version_id = create_version(finance_client, project_id)
        refused = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-CX",
            category="hard",
            source_kind="construction_forecast",
            amount=None,
        )
        assert refused.status_code == 409, refused.text


class TestShape:
    def test_a_construction_pool_is_the_hard_category(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        refused = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="SOFT-CX",
            category="soft",
            source_kind="construction_forecast",
            amount=None,
        )
        assert refused.status_code == 422, refused.text

    def test_a_construction_pool_covers_the_whole_project(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        phase_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """A phase slice of a project total would assert a split nobody decided."""
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        refused = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-CX",
            category="hard",
            source_kind="construction_forecast",
            amount=None,
            scope_kind="phase",
            phase_id=phase_id,
        )
        assert refused.status_code == 422, refused.text

    def test_hard_cost_has_one_source(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """A typed hard pool beside the forecast counts construction twice."""
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-CX",
                category="hard",
                source_kind="construction_forecast",
                amount=None,
            ).status_code
            == 201
        )
        refused = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-02",
            category="hard",
            amount="100000.00",
        )
        assert refused.status_code == 409, refused.text

    def test_a_second_construction_pool_is_refused(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-CX",
                category="hard",
                source_kind="construction_forecast",
                amount=None,
            ).status_code
            == 201
        )
        refused = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-CX2",
            category="hard",
            source_kind="construction_forecast",
            amount=None,
        )
        assert refused.status_code == 409, refused.text

    def test_a_typed_hard_pool_blocks_drawing_the_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
    ) -> None:
        """The refusal runs both ways, and names what to remove first."""
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-01",
                category="hard",
                amount="100000.00",
            ).status_code
            == 201
        )
        refused = add_pool(
            finance_client,
            project_id,
            version_id,
            pool_number="HARD-CX",
            category="hard",
            source_kind="construction_forecast",
            amount=None,
        )
        assert refused.status_code == 409, refused.text
        assert "HARD-01" in refused.json()["detail"]


class TestALaterForecastNeverRewritesHistory:
    def test_a_new_forecast_makes_a_draft_basis_stale_rather_than_moving_it(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        second_finance_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
        unit_id: str,
        land_cost: str,
    ) -> None:
        """Given / When / Then: the basis is refused, never silently re-derived."""
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="LAND-01",
                category="land",
                source_kind="project_land",
                amount=None,
            ).status_code
            == 201
        )
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-CX",
                category="hard",
                source_kind="construction_forecast",
                amount=None,
            ).status_code
            == 201
        )
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="SOFT-01",
                category="soft",
                amount="0.00",
            ).status_code
            == 201
        )
        base = f"{economics_url(project_id)}/allocation-versions/{version_id}"
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200

        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="9000000.00")

        refused = finance_client.post(f"{base}/submit", json={})
        assert refused.status_code == 409, refused.text
        assert "construction forecast" in refused.json()["detail"]

        pool = next(
            row
            for row in pools_of(finance_client, project_id, version_id)
            if row["pool_number"] == "HARD-CX"
        )
        assert pool["amount"] == "7500000.00"

    def test_recalculating_picks_up_the_current_forecast(
        self,
        finance_client: TestClient,
        cfo_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_budget: str,
        unit_id: str,
    ) -> None:
        """A draft is working state, so recalculating is the way forward."""
        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="7500000.00")
        version_id = create_version(finance_client, project_id)
        cover_required_pools(finance_client, project_id, version_id)
        remove = pools_of(finance_client, project_id, version_id)
        hard_pool = next(row for row in remove if row["pool_number"] == "HARD-01")
        dropped = finance_client.delete(
            f"{economics_url(project_id)}/allocation-versions/{version_id}/pools/{hard_pool['id']}"
        )
        assert dropped.status_code in {200, 204}, dropped.text
        assert (
            add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number="HARD-CX",
                category="hard",
                source_kind="construction_forecast",
                amount=None,
            ).status_code
            == 201
        )

        active_forecast_of(finance_client, cfo_client, project_id, cost_codes, hard="9000000.00")
        base = f"{economics_url(project_id)}/allocation-versions/{version_id}"
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200

        pool = next(
            row
            for row in pools_of(finance_client, project_id, version_id)
            if row["pool_number"] == "HARD-CX"
        )
        assert pool["amount"] == "9000000.00"
        submitted = finance_client.post(f"{base}/submit", json={})
        assert submitted.status_code == 200, submitted.text


class TestAReversalAfterTheCutoffDoesNotStaleABasis:
    def test_a_pinned_basis_survives_a_certificate_reversed_after_its_cutoff(
        self,
        db: Session,
        finance_client: TestClient,
        cfo_client: TestClient,
        manager_member_client: TestClient,
        project_id: str,
        cost_codes: dict[str, str],
        active_contract: str,
        unit_id: str,
        land_cost: str,
    ) -> None:
        """Staleness must mean the basis moved, not that a later event happened.

        The pool is drawn from a forecast taken as at two days ago, whose
        hard-cost estimate is 7,500,000 still to come plus 200,000 already
        certified. Withdrawing that certificate today is a decision made after
        the cutoff, so what that forecast is worth has not changed — and a
        submission refused here would be telling Finance to rebuild a basis that
        is still correct, on the strength of an event the forecast never
        included. Under a historical filter that read today's certificate status
        the estimate would drop to 7,500,000 and the version would be refused.
        """
        certificate = create_certificate(
            finance_client,
            project_id,
            active_contract,
            certificate_number="IPC-01",
            period_start=(date.today() - timedelta(days=35)).isoformat(),
            period_end=(date.today() - timedelta(days=6)).isoformat(),
            certificate_date=(date.today() - timedelta(days=6)).isoformat(),
        )
        assert certificate.status_code == 201, certificate.text
        certificate_id = certificate.json()["id"]
        line = set_certificate_line(
            finance_client,
            project_id,
            certificate_id,
            cost_code_id=cost_codes["hard"],
            current_work_value_ex_tax="200000.00",
        )
        assert line.status_code == 200, line.text
        certified = certify(finance_client, manager_member_client, project_id, certificate_id)
        assert certified.status_code == 200, certified.text
        backdate(
            db,
            table="construction_certificates",
            row_id=certificate_id,
            certified_at=at(date.today() - timedelta(days=5)),
        )

        active_forecast_as_at(
            finance_client,
            cfo_client,
            project_id,
            cost_codes,
            hard="7500000.00",
            as_of=date.today() - timedelta(days=2),
        )
        version_id = create_version(finance_client, project_id)
        for pool_number, category, source_kind, amount in (
            ("LAND-01", "land", "project_land", None),
            ("HARD-CX", "hard", "construction_forecast", None),
            ("SOFT-01", "soft", None, "0.00"),
        ):
            created = add_pool(
                finance_client,
                project_id,
                version_id,
                pool_number=pool_number,
                category=category,
                **({"source_kind": source_kind} if source_kind else {}),
                amount=amount,
            )
            assert created.status_code == 201, created.text
        base = f"{economics_url(project_id)}/allocation-versions/{version_id}"
        assert finance_client.post(f"{base}/calculate", json={}).status_code == 200

        pool = next(
            row
            for row in pools_of(finance_client, project_id, version_id)
            if row["pool_number"] == "HARD-CX"
        )
        assert pool["amount"] == "7700000.00"

        reversed_response = manager_member_client.post(
            f"{construction_url(project_id)}/certificates/{certificate_id}/reverse",
            json={"reason": "Withdrawn after re-measurement"},
        )
        assert reversed_response.status_code == 200, reversed_response.text

        submitted = finance_client.post(f"{base}/submit", json={})
        assert submitted.status_code == 200, submitted.text

        unchanged = next(
            row
            for row in pools_of(finance_client, project_id, version_id)
            if row["pool_number"] == "HARD-CX"
        )
        assert unchanged["amount"] == "7700000.00"


class TestConstructionNeverReachesBack:
    def test_construction_has_no_route_that_writes_a_cost_pool(self) -> None:
        """The contract is one-directional, and this is what enforces it."""
        from app.main import create_app

        paths = create_app().openapi()["paths"]
        construction_paths = [path for path in paths if "/construction" in path]
        assert construction_paths
        assert not [path for path in construction_paths if "pool" in path]

    def test_construction_does_not_import_unit_economics(self) -> None:
        import ast
        import pathlib

        imported: set[str] = set()
        for path in pathlib.Path("app/modules/construction").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
        assert not [name for name in imported if "unit_economics" in name]

    def test_the_project_summary_does_not_carry_a_unit_margin(
        self, finance_client: TestClient, project_id: str, active_budget: str
    ) -> None:
        summary = finance_client.get(f"{construction_url(project_id)}/summary").json()
        assert "margin" not in str(summary)
        assert "revenue" not in str(summary)
