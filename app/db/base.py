"""The shared SQLAlchemy declarative base and column conventions for MVP 1.0.

PR-MVP-00 deliberately defines no domain model. Business tables begin in their
assigned roadmap PRs (see docs/MVP_ROADMAP.md).

The money and rate types live here rather than in any one module because they
are a project-wide rule from `docs/ENGINEERING_RULES.md` §6, not a fact about
country configuration or about projects. Every domain that stores an amount
uses the same two.
"""

from __future__ import annotations

from sqlalchemy import MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase

#: Monetary amounts. NUMERIC always — never float, anywhere, for money.
MONEY = Numeric(18, 2)

#: Rates are stored as explicit fractions: 0.160000 means 16%. The column name
#: always ends in ``_rate_fraction`` so the unit can never be misread.
RATE = Numeric(9, 6)

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
