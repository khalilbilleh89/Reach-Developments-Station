"""Admit the construction forecast to the cost pool's source enumeration.

One constraint, replaced. This revision exists because 0009 shipped a column
wide enough to hold ``construction_forecast`` beside a CHECK that still listed
only two sources, and the database therefore refused a value from its own
enumeration with an error naming a rule nobody had broken.

The reason it is a separate revision rather than a correction to 0009 is the
only reason that matters: 0009 has been applied. A database stamped at
``0009_construction`` will never re-run it, so editing it would repair a fresh
install and leave every deployed database exactly as broken as before — while
making the two disagree about what 0009 means. A migration that has run is
history, and history is appended to.

Alembic's autogenerate is what made this possible to miss. It compares column
types, indexes and foreign keys against the models; it does not compare CHECK
constraint expressions, so widening ``source_kind`` from 16 to 24 characters was
detected and reissuing its enumeration was not. Nothing here can prevent the
next instance of that, which is why the migration tests assert the constraint by
name at 0009 and again at 0010 rather than accepting any integrity error.

The downgrade narrows the enumeration back to the two sources 0009 left, and
refuses outright if any pool is currently sourced from a construction forecast.
The alternative — deleting or rewriting those rows so the constraint fits — would
destroy a governed cost basis to make a schema change succeed, and a cost basis
that quietly lost its hard-cost pool is worse than a downgrade that stops and
says why.

Revision ID: 0010_construction_source_kind
Revises: 0009_construction
Create Date: 2026-09-03 13:22:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_construction_source_kind"
down_revision: str | Sequence[str] | None = "0009_construction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The constraint's final name, spelled once. It is what the naming convention
#: in ``app/db/base.py`` produced from the table and the ``CheckConstraint``
#: name ``source_ok``, so it is passed through ``op.f()`` at every use: without
#: that marker Alembic applies the convention *again* and emits a doubled,
#: truncated name that matches nothing, and the DROP fails on an object that
#: does not exist rather than on the one that does.
CONSTRAINT = "ck_unit_economics_cost_pools_source_ok"
TABLE = "unit_economics_cost_pools"

#: What the enumeration becomes, matching ``POOL_SOURCE_KINDS`` in
#: ``app/modules/unit_economics/models.py``.
THREE_SOURCES = "source_kind IN ('project_land', 'manual', 'construction_forecast')"

#: What 0009 left, restored on downgrade.
TWO_SOURCES = "source_kind IN ('project_land', 'manual')"


def upgrade() -> None:
    """Apply this revision."""
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, THREE_SOURCES)


def downgrade() -> None:
    """Revert this revision, or refuse rather than lose a cost basis.

    A pool sourced from a construction forecast cannot satisfy the enumeration
    0009 shipped, so narrowing the constraint under one would fail on the
    constraint's own validation — with an error about a row rather than about
    the decision being made. The check below turns that into a refusal that says
    which pools are in the way, and it deliberately does not offer to remove
    them: a cost basis whose hard-cost pool was deleted to let a schema change
    through still reconciles, still activates, and is wrong.
    """
    bind = op.get_bind()
    blocking = bind.execute(
        sa.text(
            "SELECT count(*) FROM unit_economics_cost_pools "
            "WHERE source_kind = 'construction_forecast'"
        )
    ).scalar_one()
    if blocking:
        raise RuntimeError(
            f"{blocking} cost pool(s) take their amount from a construction "
            "forecast, which the 0009 source enumeration does not admit. "
            "Downgrading would leave rows the constraint forbids, and deleting "
            "them would remove a governed hard-cost basis. Replace those pools "
            "with manual hard pools in a draft allocation version, activate it, "
            "and run this downgrade again."
        )

    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, TWO_SOURCES)
