"""The shared SQLAlchemy declarative base and column conventions for MVP 1.0.

PR-MVP-00 deliberately defines no domain model. Business tables begin in their
assigned roadmap PRs (see docs/MVP_ROADMAP.md).

The money and rate types live here rather than in any one module because they
are a project-wide rule from `docs/ENGINEERING_RULES.md` §6, not a fact about
country configuration or about projects. Every domain that stores an amount
uses the same two.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase

#: Monetary amounts. NUMERIC always — never float, anywhere, for money.
MONEY = Numeric(18, 2)

#: Rates are stored as explicit fractions: 0.160000 means 16%. The column name
#: always ends in ``_rate_fraction`` so the unit can never be misread.
RATE = Numeric(9, 6)

#: The scale of MONEY, for quantising a money figure back to it. PR-MVP-00 fixed
#: the platform's monetary scale at two decimals and every money column in the
#: system carries it, so a derived amount is rounded here rather than to
#: whatever a currency happens to declare as its minor units: an amount the
#: column cannot store is an amount that changes when it is read back.
MONEY_EXPONENT = Decimal("0.01")

#: Physical measures — areas, lengths, heights, densities. Four decimals so a
#: cadastral or surveyed area survives the round trip exactly as recorded. Here
#: rather than in one module for the same reason as MONEY and RATE: land,
#: planning and inventory all measure the same world and must agree on scale.
MEASURE = Numeric(18, 4)

#: The scale of MEASURE, for quantising a derived figure back to it. An area
#: multiplied by a six-decimal factor lands on ten decimals; presenting that is
#: false precision, and summing unquantised lines gives a total that does not
#: equal the column of figures printed above it.
MEASURE_EXPONENT = Decimal("0.0001")

#: Deterministic constraint names. Without this, PostgreSQL invents index and
#: constraint names, Alembic autogenerate cannot reference them, and downgrades
#: become guesswork.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every future domain model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def in_list(column: str, allowed: tuple[str, ...]) -> str:
    """Render a closed-set ``CHECK`` expression from the tuple defining the set.

    Writing the values twice — once as the Python tuple a service validates
    against and once as SQL — is how the two drift apart.
    """
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"
