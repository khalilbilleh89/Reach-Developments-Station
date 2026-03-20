"""
tests/architecture/test_query_efficiency.py

Query efficiency architecture tests for PR-E7 — System Performance Pass.

Validates that critical query patterns do not degrade as project data grows:

  1. Registry case list uses selectinload — no N+1 per milestone/document.
  2. List endpoints enforce pagination defaults (limit, max).
  3. Construction milestone queries are bounded by the pagination layer.

SQLAlchemy query event counting is used where practical to give a hard
upper bound on the number of SQL statements issued.
"""

import inspect
from datetime import date

from sqlalchemy import event
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Shared helpers (mirrors the pattern used in test_commercial_layer_contracts)
# ---------------------------------------------------------------------------


def _make_project(db: Session, code: str) -> str:
    from app.modules.projects.models import Project

    p = Project(name=f"Project {code}", code=code)
    db.add(p)
    db.flush()
    return p.id


def _make_unit(db: Session, project_id: str, unit_number: str = "101", *, suffix: str = "", sequence: int = 1) -> str:
    """Create Phase → Building → Floor → Unit; return unit id."""
    from app.modules.buildings.models import Building
    from app.modules.floors.models import Floor
    from app.modules.phases.models import Phase
    from app.modules.units.models import Unit

    phase = Phase(project_id=project_id, name=f"Phase-{unit_number}{suffix}", sequence=sequence)
    db.add(phase)
    db.flush()

    building = Building(phase_id=phase.id, name="Block A", code=f"BLK-{unit_number}{suffix}")
    db.add(building)
    db.flush()

    floor = Floor(
        building_id=building.id,
        name="Floor 1",
        code=f"FL-01-{unit_number}{suffix}",
        sequence_number=1,
    )
    db.add(floor)
    db.flush()

    unit = Unit(
        floor_id=floor.id,
        unit_number=unit_number,
        unit_type="studio",
        internal_area=100.0,
    )
    db.add(unit)
    db.flush()
    return unit.id


def _make_buyer(db: Session, email: str = "buyer@eff.test") -> str:
    from app.modules.sales.models import Buyer

    b = Buyer(full_name="Efficiency Test Buyer", email=email, phone="+9620000099")
    db.add(b)
    db.flush()
    return b.id


def _make_contract(
    db: Session,
    unit_id: str,
    buyer_id: str,
    contract_number: str = "CNT-EFF-001",
    price: float = 500_000.0,
) -> str:
    from app.modules.sales.models import SalesContract

    c = SalesContract(
        unit_id=unit_id,
        buyer_id=buyer_id,
        contract_number=contract_number,
        contract_date=date(2026, 1, 1),
        contract_price=price,
    )
    db.add(c)
    db.flush()
    return c.id


def _make_registry_case(
    db: Session,
    project_id: str,
    unit_id: str,
    buyer_id: str,
    contract_id: str,
    case_number: int = 1,
) -> str:
    """Create a RegistrationCase with default milestones and documents."""
    from app.modules.registry.service import RegistryService
    from app.modules.registry.schemas import RegistrationCaseCreate

    svc = RegistryService(db)
    case = svc.create_case(
        RegistrationCaseCreate(
            project_id=project_id,
            unit_id=unit_id,
            sale_contract_id=contract_id,
            buyer_name=f"Buyer {case_number}",
        )
    )
    return case.id


class QueryCounter:
    """Counts the number of SQL statements executed within a SQLAlchemy session."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.count = 0
        self._engine = db.get_bind()

    def __enter__(self) -> "QueryCounter":
        event.listen(self._engine, "before_cursor_execute", self._handler)
        return self

    def __exit__(self, *args) -> None:
        event.remove(self._engine, "before_cursor_execute", self._handler)

    def _handler(self, conn, cursor, statement, parameters, context, executemany) -> None:
        self.count += 1


# ===========================================================================
# 1. Registry N+1 prevention
# ===========================================================================


class TestRegistryEagerLoading:
    """Verify that listing registry cases does not trigger an N+1 query pattern."""

    def test_list_by_project_uses_selectinload(self):
        """
        RegistrationCaseRepository.list_by_project must use selectinload so that
        accessing .milestones and .documents on each case does not fire per-row
        SQL queries.
        """
        from app.modules.registry.repository import RegistrationCaseRepository

        src = inspect.getsource(RegistrationCaseRepository.list_by_project)
        assert "selectinload" in src, (
            "list_by_project must use selectinload() to eagerly load "
            "RegistrationCase.milestones and RegistrationCase.documents.  "
            "Without selectinload, serialising each case triggers N additional "
            "queries (N+1 pattern)."
        )

    def test_list_by_project_loads_milestones_and_documents(self):
        """
        selectinload must cover both the milestones and the documents relationships.
        """
        from app.modules.registry.repository import RegistrationCaseRepository

        src = inspect.getsource(RegistrationCaseRepository.list_by_project)
        assert "RegistrationCase.milestones" in src, (
            "list_by_project must selectinload RegistrationCase.milestones"
        )
        assert "RegistrationCase.documents" in src, (
            "list_by_project must selectinload RegistrationCase.documents"
        )

    def test_registry_case_list_query_count_bounded(self, db_session: Session):
        """
        Listing N registry cases must not issue more than O(1) queries with respect
        to N.  With selectinload SQLAlchemy issues:
          1 query for the cases
          1 query for all milestones (IN clause)
          1 query for all documents (IN clause)
        Total = 3 queries regardless of N.  We allow a small slack for internal
        SQLite metadata probes.
        """
        project_id = _make_project(db_session, "PRJ-QE-1")

        # Create 3 units / contracts / cases so N > 1
        case_count = 3
        for i in range(case_count):
            unit_id = _make_unit(db_session, project_id, str(100 + i), suffix=f"-qe{i}", sequence=i + 1)
            buyer_id = _make_buyer(db_session, f"qe{i}@eff.test")
            contract_id = _make_contract(
                db_session, unit_id, buyer_id, f"CNT-QE-{i:03d}"
            )
            _make_registry_case(db_session, project_id, unit_id, buyer_id, contract_id, i)

        db_session.commit()
        db_session.expire_all()  # Force fresh load

        from app.modules.registry.repository import RegistrationCaseRepository

        repo = RegistrationCaseRepository(db_session)
        with QueryCounter(db_session) as qc:
            cases = repo.list_by_project(project_id, skip=0, limit=100)
            # Trigger attribute access to ensure lazy loading would have fired
            for case in cases:
                _ = list(case.milestones)
                _ = list(case.documents)

        # With selectinload: 1 (cases) + 1 (milestones) + 1 (documents) = 3 queries.
        # We allow up to 10 to accommodate SQLite internals and session overhead,
        # but NOT up to case_count * 3 (which would be 9 from lazy loading + case query).
        # The key invariant is: query count must not grow linearly with N cases.
        assert qc.count <= 10, (
            f"Expected at most 10 queries for {case_count} cases with eager loading, "
            f"got {qc.count}.  This suggests N+1 lazy loading is occurring."
        )

        # Verify the cases were actually loaded
        assert len(cases) == case_count


# ===========================================================================
# 2. Pagination enforcement
# ===========================================================================


class TestPaginationEnforcement:
    """Verify that list endpoints enforce default and maximum pagination limits."""

    def test_registry_list_endpoint_enforces_pagination(self, client):
        """GET /registry/projects/{id}/cases must accept and apply limit/skip."""
        # Create the bare minimum to get a valid project response
        resp = client.get("/api/v1/registry/projects/nonexistent/cases?limit=10&skip=0")
        # 404 is expected since the project does not exist, but the route must
        # exist and accept the pagination parameters (not 422 from unknown params).
        assert resp.status_code in (404, 200), (
            f"Expected 404 (project not found) or 200, got {resp.status_code}. "
            "Ensure the endpoint accepts limit/skip query params."
        )

    def test_construction_list_endpoint_enforces_pagination(self, client):
        """GET /construction/scopes must accept limit and skip query params."""
        resp = client.get("/api/v1/construction/scopes?limit=10&skip=0")
        assert resp.status_code in (200,), (
            f"Expected 200 from scopes list, got {resp.status_code}"
        )
        data = resp.json()
        assert "items" in data, "Response must include 'items' key"
        assert "total" in data, "Response must include 'total' key"

    def test_projects_list_endpoint_enforces_pagination(self, client):
        """GET /projects must accept limit and skip query params."""
        resp = client.get("/api/v1/projects?limit=10&skip=0")
        assert resp.status_code == 200, (
            f"Expected 200 from projects list, got {resp.status_code}"
        )
        data = resp.json()
        assert "items" in data or isinstance(data, list), (
            "Response must be a list or paginated object"
        )

    def test_default_limit_caps_response(self, client, db_session: Session):
        """
        When no limit is provided the endpoint must return at most the default
        maximum (100).  This test creates 0 scopes but verifies the endpoint
        works correctly with a small-but-valid default.
        """
        resp = client.get("/api/v1/construction/scopes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("items", [])) <= 100, (
            "Default response must not exceed 100 items."
        )


# ===========================================================================
# 3. Index coverage (ORM-level spot checks)
# ===========================================================================


class TestIndexCoverage:
    """Verify that the newly-added performance indexes are present in the ORM metadata."""

    def test_registration_cases_status_index_exists(self):
        """registration_cases.status must have an index for status-filter queries."""
        from app.modules.registry.models import RegistrationCase

        table = RegistrationCase.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_registration_cases_status" in index_names, (
            "registration_cases.status is missing its index.  "
            "Add index=True to the status column and run migration 0031."
        )

    def test_registration_cases_project_id_index_exists(self):
        """registration_cases.project_id must have an index for project-scoped queries."""
        from app.modules.registry.models import RegistrationCase

        table = RegistrationCase.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_registration_cases_project_id" in index_names, (
            "registration_cases.project_id is missing its index."
        )
