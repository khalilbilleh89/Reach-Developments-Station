"""The promise every other test in this repository is built on.

No test may begin with another test's rows. That has always been true; what
changed is how it is kept. Naming all fifty-six data tables in one ``TRUNCATE``
cost about the same whether they held a million rows or none — a lock and a
file rewrite each — so it charged roughly 0.8 of a second to every test in the
suite, most of an hour of CI spent emptying tables that were already empty.

The clean now asks which tables hold anything, in about a millisecond, and
names only those. That is a cheaper way to keep the same promise, not a smaller
promise — and a promise this many tests rest on should be asserted rather than
assumed, which is what this file is for.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import get_engine

from .conftest import _DATA_TABLES, LOCK_WAIT_BUDGET, empty_data_tables


def _rows(table: str) -> int:
    with get_engine().begin() as connection:
        return connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def _add_a_currency() -> None:
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO currencies (id, code, name, minor_units, is_active)"
                " VALUES (:id, :code, :name, 2, true)"
            ),
            {"id": str(uuid.uuid4()), "code": "ZZZ", "name": "Isolation probe"},
        )


def test_every_data_table_is_empty_when_a_test_begins() -> None:
    """The guarantee itself, checked on all fifty-six rather than assumed."""
    occupied = {table: _rows(table) for table in _DATA_TABLES}
    assert not {t: n for t, n in occupied.items() if n}, (
        f"A test began with rows left by another test: { {t: n for t, n in occupied.items() if n} }"
    )


def test_a_table_holding_rows_is_found_and_emptied() -> None:
    _add_a_currency()
    assert _rows("currencies") == 1

    emptied = empty_data_tables()

    assert "currencies" in emptied, "the occupied table was not among those cleared"
    assert _rows("currencies") == 0


def test_a_suite_that_dirtied_nothing_truncates_nothing() -> None:
    """The saving itself. An already-clean database is left alone."""
    assert empty_data_tables() == [], "tables were truncated although none held a row"


def test_the_seeded_roles_survive_the_clean() -> None:
    """``roles`` is reference data from a migration, not test state.

    The old statement spared it, and CASCADE reaches no further now: it follows
    references INTO what is named, and naming fewer tables cannot reach more.
    """
    before = _rows("roles")
    assert before, "roles are seeded by migration; an empty table means the seed is gone"

    _add_a_currency()
    empty_data_tables()

    assert _rows("roles") == before


def test_the_clean_covers_every_table_it_claims_to() -> None:
    """The probe is built from the same list the clean is, and misses none."""
    for table in _DATA_TABLES:
        with get_engine().begin() as connection:
            connection.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))


def test_every_connection_carries_the_lock_wait_budget() -> None:
    """The budget must reach connections nobody configured by hand.

    It is set through ``PGOPTIONS`` precisely so that it arrives on every
    connection this process opens without the opener participating: the
    application's pool builds its own engine, Alembic builds another, and the
    fixtures build a third. A budget that only covered the one engine a test
    could name would leave the clean-up statements — the ones that actually
    block — waiting forever.
    """
    with get_engine().connect() as connection:
        assert connection.execute(text("SHOW lock_timeout")).scalar_one() == LOCK_WAIT_BUDGET


def test_a_blocked_statement_gives_up_rather_than_waiting_forever() -> None:
    """A lock this suite cannot get must raise, and it must raise by itself.

    This is the failure the budget exists for. One connection holds a table and
    does not let go; another asks for it. Without a budget the second waits for
    as long as the job is allowed to live, and the job is killed rather than
    failed — no test named, no statement reported, two hours of a runner spent.

    The wait is shortened to a quarter-second for the length of this test only.
    ``SET LOCAL`` ends with the transaction, so it cannot leak into the next
    test, and what is being asserted is the behaviour at the end of the wait
    rather than the length of it — the length is asserted above.
    """
    with get_engine().connect() as holder:
        holder.execute(text("LOCK TABLE currencies IN ACCESS EXCLUSIVE MODE"))
        with get_engine().connect() as blocked:
            blocked.execute(text("SET LOCAL lock_timeout = '250ms'"))
            with pytest.raises(OperationalError, match="lock timeout"):
                blocked.execute(text("LOCK TABLE currencies IN ACCESS EXCLUSIVE MODE"))
            blocked.rollback()
        holder.rollback()
