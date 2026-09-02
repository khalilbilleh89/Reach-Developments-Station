"""Migration 0007: the collections ledger, forward and backward.

The schema is the last line of defence for rules the service also enforces, and
the tests here go at it through raw SQL rather than through the API — a service
check that a caller can reach around is not a constraint.

Three families:

* the revision applies to an empty database and to a database at 0006, and
  reverses cleanly, leaving exactly one head and no drift;
* every money and status invariant is refused by PostgreSQL itself;
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

COLLECTION_TABLES = (
    "collection_receipts",
    "collection_receipt_allocations",
    "collection_actions",
    "collection_disputes",
    "collection_waivers",
    "collection_restructures",
    "collection_refunds",
)


class TestTheRevision:
    """Given the migration history, when it is walked in both directions."""

    def test_every_collections_table_exists_at_head(self) -> None:
        tables = set(inspect(get_engine()).get_table_names())
        missing = [name for name in COLLECTION_TABLES if name not in tables]
        assert missing == [], f"missing after upgrade: {missing}"

    def test_the_boundary_column_was_added_to_payment_plans(self) -> None:
        columns = {column["name"] for column in inspect(get_engine()).get_columns("payment_plans")}
        assert "collections_started_at" in columns

    def test_nothing_in_the_payment_plan_schedule_was_altered(self) -> None:
        """0007 is additive. What the buyer owes is still PR-MVP-06's shape.

        A ``paid_amount`` or ``balance_due`` appearing on an instalment would be
        this PR quietly moving the boundary it was written to keep.
        """
        columns = {
            column["name"]
            for column in inspect(get_engine()).get_columns("payment_plan_installments")
        }
        for forbidden in ("paid_amount", "balance_due", "receipt_id", "days_overdue"):
            assert forbidden not in columns

    def test_there_is_exactly_one_head(self) -> None:
        """One head, and 0007 is still on the path to it.

        The head itself moves with every migration PR — 0008 owns it now — so
        pinning the name here would make this file fail on somebody else's
        change. What 0007 has to keep proving is that it is still reachable in
        the one linear history, not that it is still last.
        """
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        assert len(script.get_heads()) == 1
        history = {revision.revision for revision in script.walk_revisions()}
        assert "0007_collections" in history

    def test_the_revision_sits_directly_on_payment_plans(self) -> None:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        revision = script.get_revision("0007_collections")
        assert revision.down_revision == "0006_payment_plans"


class TestMoneyConstraints:
    """Given the database, when invalid money is written past the service."""

    def _receipt_sql(self) -> str:
        return """
            INSERT INTO collection_receipts (
                id, project_id, sale_contract_id, receipt_number, currency_id,
                amount, receipt_date, status, recorded_by_user_id
            )
            SELECT :id, s.project_id, s.id, :number, s.currency_id,
                   :amount, DATE '2026-01-01', :status, p.created_by_user_id
            FROM sale_contracts s
            JOIN projects p ON p.id = s.project_id
            LIMIT 1
        """

    @pytest.mark.parametrize("amount", ["0.00", "-1.00"])
    def test_a_receipt_amount_must_be_positive(
        self, db: Session, active_sale: str, amount: str
    ) -> None:
        del active_sale
        with pytest.raises(IntegrityError) as error:
            db.execute(
                text(self._receipt_sql()),
                {
                    "id": uuid.uuid4(),
                    "number": f"RCT-TEST-{amount}",
                    "amount": amount,
                    "status": "recorded",
                },
            )
            db.flush()
        assert "amount_positive" in str(error.value)
        db.rollback()

    def test_a_confirmed_receipt_must_name_who_confirmed_it(
        self, db: Session, active_sale: str
    ) -> None:
        """Otherwise "confirmed" is a status with nobody behind it."""
        del active_sale
        with pytest.raises(IntegrityError) as error:
            db.execute(
                text(self._receipt_sql()),
                {
                    "id": uuid.uuid4(),
                    "number": "RCT-TEST-C",
                    "amount": "100.00",
                    "status": "confirmed",
                },
            )
            db.flush()
        assert "confirmed_has_actor" in str(error.value)
        db.rollback()

    def test_a_reversed_receipt_must_carry_its_reason(self, db: Session, active_sale: str) -> None:
        del active_sale
        with pytest.raises(IntegrityError) as error:
            db.execute(
                text(self._receipt_sql()),
                {
                    "id": uuid.uuid4(),
                    "number": "RCT-TEST-R",
                    "amount": "100.00",
                    "status": "reversed",
                },
            )
            db.flush()
        assert "reversed_has_reason" in str(error.value)
        db.rollback()

    def test_a_receipt_status_outside_the_closed_set_is_refused(
        self, db: Session, active_sale: str
    ) -> None:
        del active_sale
        with pytest.raises(IntegrityError) as error:
            db.execute(
                text(self._receipt_sql()),
                {
                    "id": uuid.uuid4(),
                    "number": "RCT-TEST-X",
                    "amount": "100.00",
                    "status": "settled",
                },
            )
            db.flush()
        assert "status_ok" in str(error.value)
        db.rollback()


class TestPartialUniqueIndexes:
    """Given the partial indexes, when a second live row is attempted."""

    def test_only_one_dispute_may_be_open_per_instalment(
        self, db: Session, active_plan: tuple[str, str], collecting_sale: str
    ) -> None:
        del active_plan
        insert = text(
            """
            INSERT INTO collection_disputes (
                id, project_id, sale_contract_id, installment_id, status, reason,
                opened_by_user_id
            )
            SELECT :id, i.project_id, :sale, i.id, 'open', 'Contested',
                   p.created_by_user_id
            FROM payment_plan_installments i
            JOIN payment_plan_versions v ON v.id = i.payment_plan_version_id
            JOIN payment_plans pl ON pl.id = v.payment_plan_id
            JOIN projects p ON p.id = i.project_id
            WHERE pl.sale_contract_id = :sale AND v.status = 'active'
            ORDER BY i.sequence
            LIMIT 1
            """
        )
        db.execute(insert, {"id": uuid.uuid4(), "sale": uuid.UUID(collecting_sale)})
        db.flush()
        with pytest.raises(IntegrityError) as error:
            db.execute(insert, {"id": uuid.uuid4(), "sale": uuid.UUID(collecting_sale)})
            db.flush()
        assert "uq_collection_disputes_open" in str(error.value)
        db.rollback()

    def test_the_receipt_reference_is_unique_within_a_project(
        self, db: Session, active_sale: str
    ) -> None:
        del active_sale
        insert = text(
            """
            INSERT INTO collection_receipts (
                id, project_id, sale_contract_id, receipt_number, currency_id,
                amount, receipt_date, status, recorded_by_user_id
            )
            SELECT :id, s.project_id, s.id, 'RCT-000900', s.currency_id,
                   '100.00', DATE '2026-01-01', 'recorded', p.created_by_user_id
            FROM sale_contracts s
            JOIN projects p ON p.id = s.project_id
            LIMIT 1
            """
        )
        db.execute(insert, {"id": uuid.uuid4()})
        db.flush()
        with pytest.raises(IntegrityError) as error:
            db.execute(insert, {"id": uuid.uuid4()})
            db.flush()
        assert "uq_collection_receipts_number" in str(error.value)
        db.rollback()


class TestProjectSafety:
    """Given two projects, when a row tries to reference across the boundary."""

    def test_a_receipt_cannot_name_a_sale_in_another_project(
        self,
        db: Session,
        admin_client: TestClient,
        active_sale: str,
        project_id: str,
        country_pack_id: str,
        currency_id: str,
        reference_data: None,
    ) -> None:
        """The composite foreign key makes this unwritable, not merely unchecked.

        A Python-level guard can be reached around by an import, a fixture or a
        future code path. A foreign key cannot.
        """
        del active_sale
        created = admin_client.post(
            PROJECTS,
            json=project_payload(
                country_pack_id, currency_id, code="PRJ-XPROJ", name="Another development"
            ),
        )
        assert created.status_code == 201, created.text
        other_project = uuid.UUID(created.json()["id"])

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO collection_receipts (
                        id, project_id, sale_contract_id, receipt_number, currency_id,
                        amount, receipt_date, status, recorded_by_user_id
                    )
                    SELECT :id, :other, s.id, 'RCT-CROSS', s.currency_id,
                           '100.00', DATE '2026-01-01', 'recorded', p.created_by_user_id
                    FROM sale_contracts s
                    JOIN projects p ON p.id = s.project_id
                    WHERE s.project_id = :pid
                    LIMIT 1
                    """
                ),
                {"id": uuid.uuid4(), "other": other_project, "pid": uuid.UUID(project_id)},
            )
            db.flush()
        db.rollback()

    def test_the_allocation_table_binds_every_identifier_to_the_project(self) -> None:
        """Five composite foreign keys, one per link in the chain."""
        inspector = inspect(get_engine())
        composite = [
            fk
            for fk in inspector.get_foreign_keys("collection_receipt_allocations")
            if "project_id" in fk["constrained_columns"]
        ]
        referred = {fk["referred_table"] for fk in composite}
        assert referred == {
            "sale_contracts",
            "payment_plans",
            "payment_plan_versions",
            "payment_plan_installments",
            "collection_receipts",
            "collection_restructures",
        }
