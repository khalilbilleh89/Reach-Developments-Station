"""The shared SQLAlchemy declarative base for MVP 1.0.

PR-MVP-00 deliberately defines no domain model. Business tables begin in their
assigned roadmap PRs (see docs/MVP_ROADMAP.md).
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

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
