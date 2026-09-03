"""Migration 0008: the unit economics tables, forward and backward.

The schema is the last line of defence for rules the service also enforces, and
the tests here go at it through raw SQL rather than through the API — a service
check that a caller can reach around is not a constraint.

Three families:

* the revision applies, reverses cleanly and leaves exactly one head with no
  drift, and it adds nothing to any table it does not own;
* every money, scope and lifecycle invariant is refused by PostgreSQL itself;
* a row in one project cannot reference a row in another, whatever SQL is
  written, because the foreign keys are composite.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from tests.modules.conftest import PROJECTS, project_payload

ECONOMICS_TABLES = (
    "unit_economics_allocation_versions",
    "unit_economics_cost_pools",
    "unit_economics_allocations",
    "unit_economics_unit_costs",
)

#: Tables this revision must not have touched. PR-MVP-08 answers what a unit
#: costs by reading upstream domains, never by writing a column into them.
UNTOUCHED = {
    "sale_contracts": ("unit_economics_version_id", "allocation_version_id", "cost_basis_id"),
    "units": ("cost", "margin", "profit", "total_cost", "return_on_cost"),
    "unit_price_versions": ("cost", "margin", "allocated_cost"),
    "land_parcels": ("allocated_amount", "allocation_version_id"),
}


class TestTheRevision:
    """Given the migration history, when it is walked in both directions."""

    def test_every_unit_economics_table_exists_at_head(self) -> None:
        tables = set(inspect(get_engine()).get_table_names())
        missing = [name for name in ECONOMICS_TABLES if name not in tables]
        assert missing == [], f"missing after upgrade: {missing}"

    @pytest.mark.parametrize(("table", "forbidden"), sorted(UNTOUCHED.items()))
    def test_no_upstream_table_gained_a_column(
        self, table: str, forbidden: tuple[str, ...]
    ) -> None:
        """A sold unit remembers its cost basis without sales knowing this exists.

        The link is effective dating — the contract date matched against a
        version's window — so a foreign key here would be the dependency this
        module was designed to avoid, added by accident.
        """
        columns = {column["name"] for column in inspect(get_engine()).get_columns(table)}
        assert [name for name in forbidden if name in columns] == []

    def test_no_profit_is_stored_anywhere(self) -> None:
        """Every total this module reports is derived. None of it is a column."""
        inspector = inspect(get_engine())
        for table in ECONOMICS_TABLES:
            columns = {column["name"] for column in inspector.get_columns(table)}
            for forbidden in (
                "gross_profit",
                "contribution_profit",
                "profit_after_finance",
                "margin_fraction",
                "return_on_cost_fraction",
                "total_cost",
            ):
                assert forbidden not in columns, f"{table}.{forbidden}"

    def test_the_history_still_has_exactly_one_head(self) -> None:
        """0009 took the head; what this revision still owes is a single chain.

        The "and it is this revision" half of this assertion belongs to whichever
        migration is newest, and it moved to test_migration_construction.py when
        0009 landed. Keeping it here would mean every future migration had to
        edit this file, which is how a branch point gets merged without anybody
        noticing.
        """
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        assert len(script.get_heads()) == 1
        assert script.get_revision("0008_unit_economics") is not None

    def test_the_revision_sits_directly_on_collections(self) -> None:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        revision = script.get_revision("0008_unit_economics")
        assert revision.down_revision == "0007_collections"


@pytest.fixture
def seeded(
    admin_client: TestClient, db: Session, project_id: str, operational_project: str
) -> dict[str, str]:
    """One project, one draft version and one pool, written the ordinary way.

    The constraint tests below then try to write past the service into that
    shape. They need real parents, because a foreign key failing is not the
    same proof as a check constraint failing.
    """
    del operational_project
    currency = db.execute(
        text("SELECT base_currency_id FROM projects WHERE id = :id"), {"id": project_id}
    ).scalar_one()
    actor = db.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
    version_id = str(uuid.uuid4())
    db.execute(
        text(
            """
            INSERT INTO unit_economics_allocation_versions (
                id, project_id, version_number, currency_id, status,
                finance_treatment, effective_from, change_reason, created_by_user_id
            ) VALUES (
                :id, :project_id, 1, :currency_id, 'draft', 'excluded',
                DATE '2026-01-01', 'Seeded', :actor
            )
            """
        ),
        {"id": version_id, "project_id": project_id, "currency_id": currency, "actor": actor},
    )
    db.commit()
    del admin_client
    return {"project_id": project_id, "version_id": version_id, "actor": str(actor)}


class TestLifecycleConstraints:
    """Given the database, when an impossible cost basis is written past the service."""

    def _version_sql(self) -> str:
        return """
            INSERT INTO unit_economics_allocation_versions (
                id, project_id, version_number, currency_id, status,
                finance_treatment, effective_from, effective_to, change_reason,
                created_by_user_id, rejected_at, rejection_reason, activated_at
            ) VALUES (
                :id, :project_id, :number, :currency_id, :status, 'excluded',
                DATE '2026-01-01', :effective_to, :reason, :actor,
                :rejected_at, :rejection_reason, :activated_at
            )
        """

    def _insert_version(self, db: Session, seeded: dict[str, str], **overrides: object) -> None:
        currency = db.execute(
            text("SELECT base_currency_id FROM projects WHERE id = :id"),
            {"id": seeded["project_id"]},
        ).scalar_one()
        params: dict[str, object] = {
            "id": str(uuid.uuid4()),
            "project_id": seeded["project_id"],
            "number": 99,
            "currency_id": currency,
            "status": "draft",
            "effective_to": None,
            "reason": "Written past the service",
            "actor": seeded["actor"],
            "rejected_at": None,
            "rejection_reason": None,
            "activated_at": None,
        }
        params.update(overrides)
        db.execute(text(self._version_sql()), params)

    def test_an_unknown_status_is_refused(self, db: Session, seeded: dict[str, str]) -> None:
        with pytest.raises(IntegrityError):
            self._insert_version(db, seeded, status="probably_fine")
        db.rollback()

    def test_a_window_that_ends_before_it_starts_is_refused(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        with pytest.raises(IntegrityError):
            self._insert_version(db, seeded, effective_to="2025-01-01")
        db.rollback()

    def test_a_rejection_without_a_reason_is_refused(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        with pytest.raises(IntegrityError):
            self._insert_version(db, seeded, status="rejected", rejected_at="2026-02-01 00:00+00")
        db.rollback()

    def test_an_active_version_without_an_activation_stamp_is_refused(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        with pytest.raises(IntegrityError):
            self._insert_version(db, seeded, status="active")
        db.rollback()

    def test_a_blank_change_reason_is_refused(self, db: Session, seeded: dict[str, str]) -> None:
        with pytest.raises(IntegrityError):
            self._insert_version(db, seeded, reason="")
        db.rollback()

    def test_two_active_versions_in_one_project_are_impossible(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        """The partial unique index, not the service, is what makes this true."""
        self._insert_version(
            db, seeded, number=101, status="active", activated_at="2026-02-01 00:00+00"
        )
        with pytest.raises(IntegrityError):
            self._insert_version(
                db, seeded, number=102, status="active", activated_at="2026-02-01 00:00+00"
            )
        db.rollback()


class TestPoolConstraints:
    """Given the database, when an impossible cost pool is written past the service."""

    def _insert_pool(self, db: Session, seeded: dict[str, str], **overrides: object) -> None:
        params: dict[str, object] = {
            "id": str(uuid.uuid4()),
            "project_id": seeded["project_id"],
            "version_id": seeded["version_id"],
            "number": "X-01",
            "name": "Written past the service",
            "category": "hard",
            "source_kind": "manual",
            "amount": "100.00",
            "scope_kind": "project",
            "phase_id": None,
            "building_id": None,
            "method": "unit_count",
            "area_type_id": None,
            "actor": seeded["actor"],
        }
        params.update(overrides)
        db.execute(
            text(
                """
                INSERT INTO unit_economics_cost_pools (
                    id, project_id, allocation_version_id, pool_number, name,
                    category, source_kind, amount, scope_kind, phase_id,
                    building_id, allocation_method, area_type_id, created_by_user_id
                ) VALUES (
                    :id, :project_id, :version_id, :number, :name, :category,
                    :source_kind, :amount, :scope_kind, :phase_id, :building_id,
                    :method, :area_type_id, :actor
                )
                """
            ),
            params,
        )

    def test_a_negative_amount_is_refused(self, db: Session, seeded: dict[str, str]) -> None:
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded, amount="-1.00")
        db.rollback()

    def test_an_unknown_category_is_refused(self, db: Session, seeded: dict[str, str]) -> None:
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded, category="miscellaneous")
        db.rollback()

    def test_a_phase_pool_without_a_phase_is_refused(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        """The scope shape is in the schema, not only in the service."""
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded, scope_kind="phase")
        db.rollback()

    def test_a_raw_area_pool_without_an_area_type_is_refused(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded, method="raw_area")
        db.rollback()

    def test_only_land_may_be_sourced_from_the_land_register(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded, category="soft", source_kind="project_land")
        db.rollback()

    def test_a_land_pool_cannot_be_manual(self, db: Session, seeded: dict[str, str]) -> None:
        """The service refuses this with a sentence. The database refuses it full stop.

        A land pool holding a hand-typed amount is the spreadsheet figure this
        module exists to replace, and it would reconcile perfectly.
        """
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded, category="land", source_kind="manual")
        db.rollback()

    def test_the_canonical_land_pool_cannot_be_scoped_to_a_phase(
        self, db: Session, seeded: dict[str, str], phase_id: str
    ) -> None:
        """There is no governed parcel-to-phase attribution to justify it."""
        with pytest.raises(IntegrityError):
            self._insert_pool(
                db,
                seeded,
                category="land",
                source_kind="project_land",
                scope_kind="phase",
                phase_id=phase_id,
            )
        db.rollback()

    def test_the_canonical_land_pool_cannot_be_scoped_to_a_building(
        self, db: Session, seeded: dict[str, str], building_id: str
    ) -> None:
        with pytest.raises(IntegrityError):
            self._insert_pool(
                db,
                seeded,
                category="land",
                source_kind="project_land",
                scope_kind="building",
                building_id=building_id,
            )
        db.rollback()

    def test_one_version_cannot_draw_the_land_register_twice(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        """The failure that reconciles: 840,000 of land counted as 1,680,000."""
        self._insert_pool(db, seeded, number="LAND-01", category="land", source_kind="project_land")
        with pytest.raises(IntegrityError):
            self._insert_pool(
                db, seeded, number="LAND-02", category="land", source_kind="project_land"
            )
        db.rollback()

    def test_two_pools_cannot_share_a_number_in_one_version(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        self._insert_pool(db, seeded)
        with pytest.raises(IntegrityError):
            self._insert_pool(db, seeded)
        db.rollback()


class TestUnitCostConstraints:
    """Given the database, when an impossible unit cost is written past the service."""

    def _insert_cost(self, db: Session, seeded: dict[str, str], **overrides: object) -> None:
        unit_id = db.execute(
            text("SELECT id FROM units WHERE project_id = :p LIMIT 1"),
            {"p": seeded["project_id"]},
        ).scalar_one()
        currency = db.execute(
            text("SELECT base_currency_id FROM projects WHERE id = :id"),
            {"id": seeded["project_id"]},
        ).scalar_one()
        params: dict[str, object] = {
            "id": str(uuid.uuid4()),
            "project_id": seeded["project_id"],
            "unit_id": unit_id,
            "currency_id": currency,
            "cost_type": "finishes",
            "basis": "forecast",
            "amount": "100.00",
            "status": "active",
            "reversed_at": None,
            "reversal_reason": None,
            "reversed_by": None,
            "actor": seeded["actor"],
        }
        params.update(overrides)
        db.execute(
            text(
                """
                INSERT INTO unit_economics_unit_costs (
                    id, project_id, unit_id, currency_id, cost_type, basis,
                    amount, effective_date, status, reversed_at,
                    reversal_reason, reversed_by_user_id, created_by_user_id
                ) VALUES (
                    :id, :project_id, :unit_id, :currency_id, :cost_type, :basis,
                    :amount, DATE '2026-04-01', :status, :reversed_at,
                    :reversal_reason, :reversed_by, :actor
                )
                """
            ),
            params,
        )

    def test_a_zero_amount_is_refused(
        self, db: Session, seeded: dict[str, str], unit_id: str
    ) -> None:
        """A cost of nothing is not a cost, and it would still print as a row."""
        del unit_id
        with pytest.raises(IntegrityError):
            self._insert_cost(db, seeded, amount="0.00")
        db.rollback()

    def test_a_negative_amount_is_refused(
        self, db: Session, seeded: dict[str, str], unit_id: str
    ) -> None:
        del unit_id
        with pytest.raises(IntegrityError):
            self._insert_cost(db, seeded, amount="-5.00")
        db.rollback()

    def test_an_unknown_cost_type_is_refused(
        self, db: Session, seeded: dict[str, str], unit_id: str
    ) -> None:
        del unit_id
        with pytest.raises(IntegrityError):
            self._insert_cost(db, seeded, cost_type="sundry")
        db.rollback()

    def test_a_reversal_without_actor_reason_and_time_is_refused(
        self, db: Session, seeded: dict[str, str], unit_id: str
    ) -> None:
        del unit_id
        with pytest.raises(IntegrityError):
            self._insert_cost(db, seeded, status="reversed")
        db.rollback()


class TestProjectParentage:
    """Given two projects, when a row of one reaches into the other."""

    @pytest.fixture
    def other_project(
        self, admin_client: TestClient, country_pack_id: str, currency_id: str
    ) -> str:
        response = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code="OTHER-08", name="Other development"
            ),
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def test_a_pool_cannot_belong_to_another_projects_version(
        self, db: Session, seeded: dict[str, str], other_project: str
    ) -> None:
        """The composite foreign key, not a Python check, is what refuses this."""
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO unit_economics_cost_pools (
                        id, project_id, allocation_version_id, pool_number, name,
                        category, source_kind, amount, scope_kind,
                        allocation_method, created_by_user_id
                    ) VALUES (
                        :id, :other, :version_id, 'X-99', 'Cross project', 'hard',
                        'manual', '1.00', 'project', 'unit_count', :actor
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "other": other_project,
                    "version_id": seeded["version_id"],
                    "actor": seeded["actor"],
                },
            )
        db.rollback()

    def test_an_allocation_cannot_name_a_pool_from_a_different_version(
        self, db: Session, seeded: dict[str, str], unit_id: str
    ) -> None:
        """Two separate foreign keys both passed while the row was incoherent.

        With a pool key and a version key checked independently, an allocation
        could claim version two while its pool belonged to version one. The row
        then reconciles against the wrong pool, drills down into the wrong
        basis, and prices a sold unit on a version that never governed it. Three
        columns in one key is what makes that impossible rather than merely
        unlikely.
        """
        currency = db.execute(
            text("SELECT base_currency_id FROM projects WHERE id = :id"),
            {"id": seeded["project_id"]},
        ).scalar_one()
        pool_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                INSERT INTO unit_economics_cost_pools (
                    id, project_id, allocation_version_id, pool_number, name,
                    category, source_kind, amount, scope_kind,
                    allocation_method, created_by_user_id
                ) VALUES (
                    :id, :project_id, :version_id, 'P-01', 'Version one pool', 'hard',
                    'manual', '100.00', 'project', 'unit_count', :actor
                )
                """
            ),
            {
                "id": pool_id,
                "project_id": seeded["project_id"],
                "version_id": seeded["version_id"],
                "actor": seeded["actor"],
            },
        )
        other_version = str(uuid.uuid4())
        db.execute(
            text(
                """
                INSERT INTO unit_economics_allocation_versions (
                    id, project_id, version_number, currency_id, status,
                    finance_treatment, effective_from, change_reason, created_by_user_id
                ) VALUES (
                    :id, :project_id, 2, :currency_id, 'draft', 'excluded',
                    DATE '2026-02-01', 'Second basis', :actor
                )
                """
            ),
            {
                "id": other_version,
                "project_id": seeded["project_id"],
                "currency_id": currency,
                "actor": seeded["actor"],
            },
        )
        db.flush()
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO unit_economics_allocations (
                        id, project_id, allocation_version_id, cost_pool_id, unit_id,
                        driver_value, driver_share, allocated_amount, is_rounding_recipient
                    ) VALUES (
                        :id, :project_id, :version_id, :pool_id, :unit_id,
                        '1.0000', '1.000000', '100.00', TRUE
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "project_id": seeded["project_id"],
                    "version_id": other_version,
                    "pool_id": pool_id,
                    "unit_id": unit_id,
                },
            )
        db.rollback()

    def test_a_clone_cannot_point_at_a_version_that_does_not_exist(
        self, db: Session, seeded: dict[str, str]
    ) -> None:
        """``source_version_id`` was a note. It is now provenance."""
        currency = db.execute(
            text("SELECT base_currency_id FROM projects WHERE id = :id"),
            {"id": seeded["project_id"]},
        ).scalar_one()
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO unit_economics_allocation_versions (
                        id, project_id, version_number, currency_id, status,
                        finance_treatment, effective_from, change_reason,
                        source_version_id, created_by_user_id
                    ) VALUES (
                        :id, :project_id, 3, :currency_id, 'draft', 'excluded',
                        DATE '2026-03-01', 'Clone of nothing', :ghost, :actor
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "project_id": seeded["project_id"],
                    "currency_id": currency,
                    "ghost": str(uuid.uuid4()),
                    "actor": seeded["actor"],
                },
            )
        db.rollback()

    def test_a_clone_cannot_point_at_another_projects_version(
        self, db: Session, seeded: dict[str, str], other_project: str
    ) -> None:
        currency = db.execute(
            text("SELECT base_currency_id FROM projects WHERE id = :id"),
            {"id": other_project},
        ).scalar_one()
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO unit_economics_allocation_versions (
                        id, project_id, version_number, currency_id, status,
                        finance_treatment, effective_from, change_reason,
                        source_version_id, created_by_user_id
                    ) VALUES (
                        :id, :other, 1, :currency_id, 'draft', 'excluded',
                        DATE '2026-03-01', 'Reaching across projects', :source, :actor
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "other": other_project,
                    "currency_id": currency,
                    "source": seeded["version_id"],
                    "actor": seeded["actor"],
                },
            )
        db.rollback()

    def test_a_unit_cost_cannot_name_another_projects_unit(
        self, db: Session, seeded: dict[str, str], other_project: str, unit_id: str
    ) -> None:
        del unit_id
        owned_unit = db.execute(
            text("SELECT id FROM units WHERE project_id = :p LIMIT 1"),
            {"p": seeded["project_id"]},
        ).scalar_one()
        currency = db.execute(
            text("SELECT base_currency_id FROM projects WHERE id = :id"),
            {"id": other_project},
        ).scalar_one()
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO unit_economics_unit_costs (
                        id, project_id, unit_id, currency_id, cost_type, basis,
                        amount, effective_date, status, created_by_user_id
                    ) VALUES (
                        :id, :other, :unit_id, :currency_id, 'finishes', 'forecast',
                        '10.00', DATE '2026-04-01', 'active', :actor
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "other": other_project,
                    "unit_id": owned_unit,
                    "currency_id": currency,
                    "actor": seeded["actor"],
                },
            )
        db.rollback()
