"""0011, and the shape it leaves behind.

The deployed path, not just a fresh install. ``0010 -> 0011`` on a database that
already carries the construction module is what a running system will actually
do, and it is a different question from ``empty -> head`` — a revision can be
right on one and wrong on the other, which is precisely the defect PR-MVP-09's
0010 was written to correct.

The constraints are asserted by name and by expression rather than by "some
error occurred". A test satisfied by any integrity violation passes while the
*wrong* rule refuses the row, and nobody notices until the right rule is gone.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]

HEAD_REVISION = "0011_cashflow_reporting"
CONSTRUCTION_REVISION = "0010_construction_source_kind"

#: The tables 0011 creates. Named so a revision that quietly drops one is caught
#: here rather than by the first request that needs it.
CASHFLOW_TABLES = (
    "cashflow_forecast_versions",
    "cashflow_forecast_lines",
    "cashflow_customer_schedule_snapshots",
    "cashflow_development_movements",
    "cashflow_financing_movements",
    "cashflow_receipt_restrictions",
    "cashflow_restriction_releases",
)


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "app" / "db" / "migrations"))
    return config


def _script() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config())


@pytest.fixture
def at_construction_revision(postgres: None) -> Iterator[None]:
    """A database carrying construction but not cashflow — a real deployment."""
    del postgres
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, CONSTRUCTION_REVISION)
    try:
        yield
    finally:
        command.upgrade(config, "head")


def _tables() -> set[str]:
    with get_engine().connect() as connection:
        return {
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }


def _constraint_expression(*, table: str, name: str) -> str | None:
    with get_engine().connect() as connection:
        return connection.execute(
            text(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = :table AND c.conname = :name"
            ),
            {"table": table, "name": name},
        ).scalar()


def _index_definition(name: str) -> str | None:
    with get_engine().connect() as connection:
        return connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
            {"name": name},
        ).scalar()


class TestTheRevisionGraph:
    def test_there_is_exactly_one_head(self) -> None:
        assert len(_script().get_heads()) == 1

    def test_cashflow_sits_directly_on_the_construction_correction(self) -> None:
        assert _script().get_revision(HEAD_REVISION).down_revision == CONSTRUCTION_REVISION

    def test_the_construction_revisions_are_untouched(self) -> None:
        """0009 and 0010 are applied history, and this PR appends to it."""
        script = _script()
        assert script.get_revision("0009_construction").down_revision == "0008_unit_economics"
        assert script.get_revision(CONSTRUCTION_REVISION).down_revision == "0009_construction"


class TestTheDeployedPath:
    def test_a_construction_database_gains_the_cashflow_tables(
        self, at_construction_revision: None
    ) -> None:
        """Given / When / Then: the upgrade a running system will actually run."""
        assert not _tables() & set(CASHFLOW_TABLES)
        command.upgrade(_alembic_config(), HEAD_REVISION)
        assert set(CASHFLOW_TABLES) <= _tables()

    def test_the_upgrade_can_be_taken_back_and_reapplied(
        self, at_construction_revision: None
    ) -> None:
        config = _alembic_config()
        command.upgrade(config, HEAD_REVISION)
        command.downgrade(config, CONSTRUCTION_REVISION)
        assert not _tables() & set(CASHFLOW_TABLES)
        command.upgrade(config, HEAD_REVISION)
        assert set(CASHFLOW_TABLES) <= _tables()

    def test_taking_it_back_leaves_construction_standing(
        self, at_construction_revision: None
    ) -> None:
        """Nothing here is shared, so no other module loses a column."""
        config = _alembic_config()
        command.upgrade(config, HEAD_REVISION)
        command.downgrade(config, CONSTRUCTION_REVISION)
        remaining = _tables()
        assert "construction_forecast_versions" in remaining
        assert "unit_economics_cost_pools" in remaining


class TestTheSchemaHoldsTheRules:
    def test_one_active_and_one_open_forecast_per_project(self, postgres: None) -> None:
        """Held by partial unique indexes, not by a service that remembers."""
        del postgres
        active = _index_definition("uq_cf_forecasts_one_active")
        assert active is not None
        assert "UNIQUE" in active
        # PostgreSQL renders the predicate with its own casts, so the assertion
        # is on the value rather than on the exact text it prints back.
        assert "'active'" in active
        assert "status" in active

        open_index = _index_definition("uq_cf_forecasts_one_open")
        assert open_index is not None
        assert "UNIQUE" in open_index
        for status in ("draft", "submitted", "approved"):
            assert status in open_index

    def test_one_standing_restriction_per_receipt(self, postgres: None) -> None:
        """Two would each be checked against the receipt alone and together exceed it."""
        del postgres
        index = _index_definition("uq_cf_restriction_one_standing")
        assert index is not None
        assert "UNIQUE" in index
        assert "recorded" in index
        assert "confirmed" in index

    @pytest.mark.parametrize(
        "table",
        [
            "cashflow_development_movements",
            "cashflow_financing_movements",
            "cashflow_restriction_releases",
        ],
    )
    def test_the_confirmer_is_never_the_recorder(self, postgres: None, table: str) -> None:
        """By user identifier. A role comparison would let one person do both."""
        del postgres
        expression = _constraint_expression(
            table=table, name=f"ck_{table}_confirmer_is_not_recorder"
        )
        assert expression is not None
        assert "confirmed_by_user_id" in expression
        assert "recorded_by_user_id" in expression

    def test_a_construction_forecast_line_must_name_a_cost_code(self, postgres: None) -> None:
        """Without one the reconciliation has nothing to group by."""
        del postgres
        expression = _constraint_expression(
            table="cashflow_forecast_lines",
            name="ck_cashflow_forecast_lines_source_shape_ok",
        )
        assert expression is not None
        assert "construction_cost_code_id IS NOT NULL" in expression

    def test_a_financing_movement_direction_follows_its_type(self, postgres: None) -> None:
        del postgres
        expression = _constraint_expression(
            table="cashflow_financing_movements",
            name="ck_cashflow_financing_movements_direction_matches_type",
        )
        assert expression is not None
        assert "equity_contribution" in expression
        assert "'inflow'" in expression

    def test_a_period_month_is_the_first_of_its_month(self, postgres: None) -> None:
        """15 March and 1 March in one column is two rows nothing will group."""
        del postgres
        expression = _constraint_expression(
            table="cashflow_forecast_lines",
            name="ck_cashflow_forecast_lines_month_canonical",
        )
        assert expression is not None
        assert "day" in expression.lower()


class TestTheSchemaRefusesTheImpossibleRow:
    def test_a_negative_restriction_is_refused_by_name(self, postgres: None) -> None:
        """Asserted against the specific constraint, never against "some error"."""
        del postgres
        with pytest.raises(IntegrityError) as raised, get_engine().begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO cashflow_receipt_restrictions "
                    "(id, project_id, receipt_id, restricted_amount, reason, status,"
                    " recorded_by_user_id) VALUES "
                    "(gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), -1, 'x',"
                    " 'recorded', gen_random_uuid())"
                )
            )
        assert "ck_cashflow_receipt_restrictions_amount_nonneg" in str(raised.value)

    def test_a_financing_movement_pointing_the_wrong_way_is_refused_by_name(
        self, postgres: None
    ) -> None:
        del postgres
        with pytest.raises(IntegrityError) as raised, get_engine().begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO cashflow_financing_movements "
                    "(id, project_id, movement_reference, movement_type, flow_direction,"
                    " amount, currency_id, movement_date, status, recorded_by_user_id)"
                    " VALUES (gen_random_uuid(), gen_random_uuid(), 'FIN-X',"
                    " 'equity_contribution', 'outflow', 1, gen_random_uuid(),"
                    " CURRENT_DATE, 'recorded', gen_random_uuid())"
                )
            )
        assert "direction_matches_type" in str(raised.value)
